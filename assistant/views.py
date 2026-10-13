from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import process_chat

class ChatView(APIView):
    def post(self, request, *args, **kwargs):
        session_id = request.data.get('session_id')
        dealer_id = request.data.get('dealer_id')
        message = request.data.get('message')
        
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            
        if not message:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "message is required", "details": []}}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            result = process_chat(session_id, dealer_id, message)
            return Response(result)
        except Exception as e:
            # Graceful fallback: return 200 with a polite message, not 500
            return Response({
                "reply": "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment.",
                "cited_skus": [],
                "tool_calls": [],
                "actions": [],
                "session_id": session_id
            }, status=status.HTTP_200_OK)
