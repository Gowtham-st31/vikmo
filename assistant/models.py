from django.db import models
from dealers.models import Dealer

class ChatSession(models.Model):
    session_id = models.CharField(max_length=255, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    dealer = models.ForeignKey(Dealer, on_delete=models.SET_NULL, null=True)

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=50) # 'user', 'assistant', 'system', 'tool'
    content = models.TextField(blank=True, null=True)
    tool_calls = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
