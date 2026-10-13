"""
DealerDesk Demand Forecast
--------------------------
Produces ml/forecast.csv with 4-week-ahead weekly forecasts for all 40 lead-time
SKUs.  Approach:

  1. **Features** – trend (from a FIXED origin), week-of-year, promo_flag,
     weeks-to-Diwali / weeks-since-Diwali, one-hot category + SKU dummies.
  2. **Models** – Ridge regression, recent 4-week average, same-week-last-year
     (SWLY) scaled by recent sales level.
  3. **Blend** – three-way weighted blend (Avg, SWLY-scaled, Ridge) chosen by
     time-series cross-validation (rolling-origin backtest over 6 folds including
     pre-Diwali and post-Diwali windows).
  4. **Intermittent / new SKUs** – SKUs with > 50% zero-sales weeks use
     Croston's method with Syntetos-Boylan Approximation (SBA); brand-new
     SKUs with zero history get the category average.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
import os
import warnings

warnings.filterwarnings('ignore')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
ML_DIR = os.path.dirname(__file__)

# Fixed trend origin – keeps training and forecast rows comparable
TREND_ORIGIN = pd.Timestamp('2024-09-30')

# Ridge regularisation – same alpha used in backtest AND final model
RIDGE_ALPHA = 10.0


# ── Metrics ──────────────────────────────────────────────────────────────
def wape(y_true, y_pred):
    total = np.sum(np.abs(y_true))
    if total == 0:
        return 0.0
    return float(np.sum(np.abs(y_true - y_pred)) / total)


# ── Croston's Method with Syntetos-Boylan Approximation (SBA) ─────────────
def croston_sba(series, alpha=0.1):
    """
    Croston's method with Syntetos-Boylan Approximation (SBA) for intermittent demand.
    Estimates non-zero demand size and inter-demand intervals, debiasing by (1 - alpha/2).
    """
    series = np.array(series, dtype=float)
    non_zeros = np.where(series > 0)[0]
    if len(non_zeros) == 0:
        return 0.0
    z = series[non_zeros[0]]
    p = 1.0
    last_idx = non_zeros[0]
    for idx in non_zeros[1:]:
        q = idx - last_idx
        y = series[idx]
        z = alpha * y + (1.0 - alpha) * z
        p = alpha * q + (1.0 - alpha) * p
        last_idx = idx
    if p == 0:
        return float(z)
    return float((1.0 - alpha / 2.0) * (z / p))


# ── Feature Engineering ─────────────────────────────────────────────────
def create_features(df, catalogue, festivals):
    df = df.copy()
    df['week_start'] = pd.to_datetime(df['week_start'])
    df['week_of_year'] = df['week_start'].dt.isocalendar().week.astype(int)
    df['month'] = df['week_start'].dt.month

    # Distance to Diwali
    df['weeks_to_diwali'] = 52.0
    df['weeks_since_diwali'] = 52.0

    for _, row in festivals.iterrows():
        diwali_date = pd.to_datetime(row['date'])
        diff_days = (diwali_date - df['week_start']).dt.days
        diff_weeks = diff_days / 7.0

        mask_to = (diff_weeks >= 0) & (diff_weeks <= 12)
        df.loc[mask_to, 'weeks_to_diwali'] = diff_weeks[mask_to]

        mask_since = (diff_weeks < 0) & (diff_weeks >= -12)
        df.loc[mask_since, 'weeks_since_diwali'] = -diff_weeks[mask_since]

    df = df.merge(catalogue[['sku', 'category']], on='sku', how='left')

    # Global trend from fixed origin
    df['trend'] = (df['week_start'] - TREND_ORIGIN).dt.days / 7.0

    return df


def _compute_swly_scaled(train, test, sales_all):
    """
    Same-week-last-year scaled by the ratio of recent sales level to last-year's
    recent level, so it doesn't just copy last year's volume verbatim.
    """
    test = test.copy()
    # Look up last-year actuals
    test['ly_week'] = test['week_start'] - pd.Timedelta(days=364)
    ly_sales = sales_all[['sku', 'week_start', 'units_sold']].rename(
        columns={'week_start': 'ly_week', 'units_sold': 'ly_units'})
    test = test.merge(ly_sales, on=['sku', 'ly_week'], how='left')

    # Recent 4-week average (current period)
    cutoff = train['week_start'].max()
    recent_avg = (train[train['week_start'] > cutoff - pd.Timedelta(days=7 * 4)]
                  .groupby('sku')['units_sold'].mean())

    # Same 4-week window one year ago
    ly_cutoff = cutoff - pd.Timedelta(days=364)
    ly_recent = (sales_all[(sales_all['week_start'] > ly_cutoff - pd.Timedelta(days=7 * 4)) &
                           (sales_all['week_start'] <= ly_cutoff)]
                 .groupby('sku')['units_sold'].mean())

    # Scaling ratio per SKU: recent_level / last_year_level (capped to avoid blowups)
    scale = (recent_avg / ly_recent).replace([np.inf, -np.inf], 1.0).fillna(1.0).clip(0.2, 5.0)
    test['ly_scale'] = test['sku'].map(scale).fillna(1.0)
    test['pred_swly'] = (test['ly_units'].fillna(0) * test['ly_scale'])

    # Fallback: if no LY data, use recent average
    missing_ly = test['ly_units'].isna()
    if missing_ly.any():
        avg_map = recent_avg.to_dict()
        test.loc[missing_ly, 'pred_swly'] = test.loc[missing_ly, 'sku'].map(avg_map).fillna(0)

    return test


# ── Main ─────────────────────────────────────────────────────────────────
def run():
    print("Loading data...")
    sales = pd.read_csv(os.path.join(DATA_DIR, 'sales_history.csv'))
    promo = pd.read_csv(os.path.join(DATA_DIR, 'promo_calendar.csv'))
    lead_times = pd.read_csv(os.path.join(DATA_DIR, 'lead_times.csv'))
    festivals = pd.read_csv(os.path.join(DATA_DIR, 'festival_calendar.csv'))
    catalogue = pd.read_csv(os.path.join(DATA_DIR, 'catalogue.csv'))

    print("Creating features...")
    sales = create_features(sales, catalogue, festivals)

    target_skus = set(lead_times['sku'].unique())

    # ── Identify intermittent SKUs (zero-share > 50% of history weeks) ───
    sku_totals = sales.groupby('sku').size()
    sku_zeros = sales[sales['units_sold'] == 0].groupby('sku').size().reindex(sku_totals.index, fill_value=0)
    sku_zero_share = sku_zeros / sku_totals
    intermittent_skus = set(sku_zero_share[sku_zero_share > 0.5].index)
    global_median = float(sales['units_sold'].median())
    print(f"Intermittent SKUs (>50% zero weeks): {len(intermittent_skus)} ({sorted(list(intermittent_skus))})")

    # Category averages for new / zero-history SKUs
    cat_avg = sales.groupby('category')['units_sold'].mean()

    # ── Build one-hot dummies on training data ───────────────────────────
    feature_base = ['trend', 'week_of_year', 'promo_flag',
                    'weeks_to_diwali', 'weeks_since_diwali']

    cat_dummies = pd.get_dummies(sales['category'], prefix='cat')
    sales = pd.concat([sales, cat_dummies], axis=1)
    cat_cols = list(cat_dummies.columns)

    sku_dummies = pd.get_dummies(sales['sku'], prefix='sku')
    sales = pd.concat([sales, sku_dummies], axis=1)
    sku_cols = list(sku_dummies.columns)

    feature_cols = feature_base + cat_cols + sku_cols

    # ── Backtest (6 folds, including pre- and post-Diwali 2025 windows) ───
    max_date = sales['week_start'].max()
    cutoffs = [
        pd.Timestamp('2025-09-22'),  # 4-week window before Diwali 2025-10-21
        pd.Timestamp('2025-10-20'),  # 4-week window after Diwali 2025-10-21
        max_date - pd.Timedelta(days=7 * 16),  # 2026-06-01
        max_date - pd.Timedelta(days=7 * 12),  # 2026-06-29
        max_date - pd.Timedelta(days=7 * 8),   # 2026-07-27
        max_date - pd.Timedelta(days=7 * 4),   # 2026-08-24
    ]

    # ── Grid search over 3-way blend weights ─────────────────────────────
    # w_avg + w_swly + w_ridge = 1.0, each in [0.0, 0.1, ..., 0.6]
    print("\nRunning backtest over 3-way blend grid (Avg, SWLY-scaled, Ridge)...")
    blend_wapes = []
    weight_step = 0.1
    weight_range = [round(x * weight_step, 1) for x in range(7)]  # 0.0..0.6

    for avg_w in weight_range:
        for swly_w in weight_range:
            ridge_w = round(1.0 - avg_w - swly_w, 2)
            if ridge_w < -0.001 or ridge_w > 1.001:
                continue  # invalid combo
            ridge_w = max(0.0, ridge_w)

            fold_wapes = []
            for cutoff in cutoffs:
                train = sales[sales['week_start'] <= cutoff]
                test = sales[(sales['week_start'] > cutoff) &
                             (sales['week_start'] <= cutoff + pd.Timedelta(days=7 * 4))].copy()
                if test.empty:
                    continue

                # Identify intermittent SKUs within the fold's training history
                train_tot = train.groupby('sku').size()
                train_zeros = train[train['units_sold'] == 0].groupby('sku').size().reindex(train_tot.index, fill_value=0)
                fold_intermittent = set((train_zeros / train_tot)[(train_zeros / train_tot) > 0.5].index)

                # Recent 4-week average
                recent_avg = (train[train['week_start'] > cutoff - pd.Timedelta(days=7 * 4)]
                              .groupby('sku')['units_sold'].mean().reset_index()
                              .rename(columns={'units_sold': 'pred_avg'}))
                test = test.merge(recent_avg, on='sku', how='left')
                test['pred_avg'] = test['pred_avg'].fillna(0)

                # SWLY-scaled
                test = _compute_swly_scaled(train, test, sales)

                # Ridge
                model = Ridge(alpha=RIDGE_ALPHA)
                X_train = train[feature_cols].fillna(0)
                y_train = train['units_sold']
                model.fit(X_train, y_train)
                X_test = test[feature_cols].fillna(0)
                test['pred_ridge'] = np.maximum(0, model.predict(X_test))

                # Three-way blend
                test['pred_blend'] = (avg_w * test['pred_avg']
                                      + swly_w * test['pred_swly']
                                      + ridge_w * test['pred_ridge'])

                # Apply Croston/SBA on intermittent SKUs
                for sku in fold_intermittent:
                    sku_train_series = train[train['sku'] == sku].sort_values('week_start')['units_sold'].values
                    sba_val = croston_sba(sku_train_series)
                    test.loc[test['sku'] == sku, 'pred_blend'] = sba_val

                fold_wapes.append(wape(test['units_sold'].values, test['pred_blend'].values))

            mean_wape = np.mean(fold_wapes)
            blend_wapes.append((avg_w, swly_w, ridge_w, mean_wape))

    # Pick the best weight triple
    blend_wapes.sort(key=lambda x: x[3])
    best_avg_w, best_swly_w, best_ridge_w, best_wape = blend_wapes[0]
    print(f"\nBest blend weights chosen by CV: Avg={best_avg_w:.0%}, SWLY={best_swly_w:.0%}, Ridge={best_ridge_w:.0%}  (Mean WAPE={best_wape:.4f})")
    # Show top-5 for reference
    print("Top-5 blend candidates:")
    for aw, sw, rw, mw in blend_wapes[:5]:
        print(f"  Avg={aw:.0%} SWLY={sw:.0%} Ridge={rw:.0%} -> WAPE={mw:.4f}")

    # Print the full honest backtest table with the chosen weights
    print("\n" + "=" * 72)
    print(f"{'Cutoff':<14} {'Last':>8} {'Avg4w':>8} {'SWLY':>8} {'Ridge':>8} {'Blend':>8}")
    print("-" * 72)
    for cutoff in cutoffs:
        train = sales[sales['week_start'] <= cutoff]
        test = sales[(sales['week_start'] > cutoff) &
                     (sales['week_start'] <= cutoff + pd.Timedelta(days=7 * 4))].copy()
        if test.empty:
            continue

        train_tot = train.groupby('sku').size()
        train_zeros = train[train['units_sold'] == 0].groupby('sku').size().reindex(train_tot.index, fill_value=0)
        fold_intermittent = set((train_zeros / train_tot)[(train_zeros / train_tot) > 0.5].index)

        # Last value
        last_val = (train.sort_values('week_start').groupby('sku').last()[['units_sold']]
                    .reset_index().rename(columns={'units_sold': 'pred_last'}))
        test = test.merge(last_val, on='sku', how='left')
        test['pred_last'] = test['pred_last'].fillna(0)

        # Recent average
        recent_avg = (train[train['week_start'] > cutoff - pd.Timedelta(days=7 * 4)]
                      .groupby('sku')['units_sold'].mean().reset_index()
                      .rename(columns={'units_sold': 'pred_avg'}))
        test = test.merge(recent_avg, on='sku', how='left')
        test['pred_avg'] = test['pred_avg'].fillna(0)

        # Same-week-last-year (scaled)
        test = _compute_swly_scaled(train, test, sales)

        # Ridge
        model = Ridge(alpha=RIDGE_ALPHA)
        X_train = train[feature_cols].fillna(0)
        y_train = train['units_sold']
        model.fit(X_train, y_train)
        X_test = test[feature_cols].fillna(0)
        test['pred_ridge'] = np.maximum(0, model.predict(X_test))

        # Three-way blend
        test['pred_blend'] = (best_avg_w * test['pred_avg']
                              + best_swly_w * test['pred_swly']
                              + best_ridge_w * test['pred_ridge'])

        for sku in fold_intermittent:
            sku_train_series = train[train['sku'] == sku].sort_values('week_start')['units_sold'].values
            sba_val = croston_sba(sku_train_series)
            test.loc[test['sku'] == sku, 'pred_blend'] = sba_val

        w_last = wape(test['units_sold'].values, test['pred_last'].values)
        w_avg  = wape(test['units_sold'].values, test['pred_avg'].values)
        w_swly = wape(test['units_sold'].values, test['pred_swly'].values)
        w_rdg  = wape(test['units_sold'].values, test['pred_ridge'].values)
        w_bld  = wape(test['units_sold'].values, test['pred_blend'].values)

        print(f"{str(cutoff.date()):<14} {w_last:8.4f} {w_avg:8.4f} {w_swly:8.4f} {w_rdg:8.4f} {w_bld:8.4f}")
    print("=" * 72)

    # ── Train final model and produce forecast ───────────────────────────
    print("\nTraining final model and generating forecast...")
    model = Ridge(alpha=RIDGE_ALPHA)
    X_full = sales[feature_cols].fillna(0)
    y_full = sales['units_sold']
    model.fit(X_full, y_full)

    # Prepare forecast frame
    forecast_df = promo.copy()
    forecast_df = create_features(forecast_df, catalogue, festivals)

    forecast_cat_dummies = pd.get_dummies(forecast_df['category'], prefix='cat')
    forecast_df = pd.concat([forecast_df, forecast_cat_dummies], axis=1)

    forecast_sku_dummies = pd.get_dummies(forecast_df['sku'], prefix='sku')
    forecast_df = pd.concat([forecast_df, forecast_sku_dummies], axis=1)

    for col in feature_cols:
        if col not in forecast_df.columns:
            forecast_df[col] = 0

    X_forecast = forecast_df[feature_cols].fillna(0)
    forecast_df['pred_ridge'] = np.maximum(0, model.predict(X_forecast))

    # Recent average for the blend
    recent_avg = (sales[sales['week_start'] > max_date - pd.Timedelta(days=7 * 4)]
                  .groupby('sku')['units_sold'].mean().reset_index()
                  .rename(columns={'units_sold': 'pred_avg'}))
    forecast_df = forecast_df.merge(recent_avg, on='sku', how='left')
    forecast_df['pred_avg'] = forecast_df['pred_avg'].fillna(0)

    # SWLY-scaled for final forecast
    forecast_df = _compute_swly_scaled(sales, forecast_df, sales)

    # Three-way blend
    forecast_df['forecast_units'] = (best_avg_w * forecast_df['pred_avg']
                                     + best_swly_w * forecast_df['pred_swly']
                                     + best_ridge_w * forecast_df['pred_ridge'])

    # Handle intermittent SKUs (> 50% zero weeks) using Croston/SBA
    for sku in intermittent_skus:
        sku_series = sales[sales['sku'] == sku].sort_values('week_start')['units_sold'].values
        sba_val = croston_sba(sku_series)
        mask = forecast_df['sku'] == sku
        forecast_df.loc[mask, 'forecast_units'] = sba_val

    # Handle new SKUs with zero history – fall back to category average
    skus_in_sales = set(sales['sku'].unique())
    for sku in target_skus:
        if sku not in skus_in_sales:
            mask = forecast_df['sku'] == sku
            if mask.any():
                cat = forecast_df.loc[mask, 'category'].iloc[0]
                forecast_df.loc[mask, 'forecast_units'] = cat_avg.get(cat, global_median)

    # Filter to target SKUs
    forecast_df = forecast_df[forecast_df['sku'].isin(target_skus)]

    out_cols = ['sku', 'week_start', 'forecast_units']
    out_df = forecast_df[out_cols].sort_values(['sku', 'week_start'])

    out_path = os.path.join(ML_DIR, 'forecast.csv')
    out_df.to_csv(out_path, index=False)
    print(f"Saved forecast to {out_path} ({len(out_df)} rows)")


if __name__ == "__main__":
    run()
