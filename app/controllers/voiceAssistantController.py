"""
app/controllers/voiceAssistantController.py - Main Voice Assistant Business Logic
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

import google.generativeai as genai

from ..services.gemini_service import get_gemini_service
from ..services.session_service import get_session_service
from ..services.municipal_api_service import get_municipal_api_service

class VoiceAssistantController:
    def __init__(self):
        self.gemini_service = get_gemini_service()
        self.session_service = get_session_service()
        self.api_service = get_municipal_api_service()
    
    async def process_text_message(self, session, user_message: str) -> str:
        """Process a text message and return response"""
        try:
            print(f"👤 User ({session.platform}): {user_message}")
            
            # Update session activity
            session.update_activity()
            
            # Build context from chat history (but don't include in response)
            context_prompt = self.session_service.build_context_prompt(session)
            
            # Add authentication context to the prompt (for Gemini only, not user)
            auth_status = session.get_auth_status()
            
            # Check if this is a voice call session and handle auto-login
            if session.platform in ["voice", "whatsapp_call"] and not auth_status['authenticated']:
                # Auto-authenticate for voice calls using phone number
                if hasattr(session, 'caller_number') and session.caller_number:
                    await self._auto_authenticate_by_mobile(session, session.caller_number)
                    auth_status = session.get_auth_status()  # Refresh status
            
            # Create internal auth context for Gemini (not shown to user)
            internal_auth_context = f"""
INTERNAL CONTEXT (DO NOT INCLUDE IN RESPONSE):
Current session authentication status:
- Authenticated: {auth_status['authenticated']}
- Auth Step: {auth_status['auth_step']}
- Pending Mobile: {auth_status.get('mobile', 'None')}
- User ID: {auth_status.get('user_id', 'None')}
- Platform: {auth_status.get('platform', 'web')}

Authentication Rules:
1. For voice/whatsapp_call platforms: Users are auto-authenticated by phone number
2. For web/whatsapp platforms: Require OTP authentication
3. If auth_step is "NEED_MOBILE": Ask for mobile number first
4. If auth_step is "NEED_OTP": Ask for OTP code
5. If auth_step is "AUTHENTICATED": Provide full services
6. Do not provide any services until user is authenticated

IMPORTANT: Only respond with the actual message to the user. Do not include any of this internal context in your response.
"""
            
            # Prepare the full message with context for Gemini processing
            if context_prompt:
                full_message = f"{internal_auth_context}\n{context_prompt}\n\nCurrent user message: {user_message}"
            else:
                full_message = f"{internal_auth_context}\n\nCurrent user message: {user_message}"
            
            # Send message to Gemini
            if not session.chat:
                session._init_gemini_chat()
            
            response = session.chat.send_message(full_message)
            
            # Process function calls and get final response
            response_text, function_calls = await self._process_gemini_response(session, response)
            
            # Clean up any leaked internal context from the response
            response_text = self._clean_response_text(response_text)
            
            # Add messages to session history
            session.add_message("user", user_message)
            session.add_message("assistant", response_text, function_calls)
            
            print(f"🤖 Bot response: {response_text}")
            
            return response_text
            
        except Exception as e:
            print(f"❌ Error processing message: {str(e)}")
            return f"I'm sorry, I encountered an error: {str(e)}. Please try again."
    
    def _clean_response_text(self, response_text: str) -> str:
        """Remove any leaked internal context from the response"""
        # Remove lines that look like internal context
        lines = response_text.split('\n')
        cleaned_lines = []
        
        skip_line = False
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip lines that contain internal context markers
            if any(marker in line_lower for marker in [
                'current session authentication',
                'authentication status:',
                '- authenticated:',
                '- auth step:',
                '- pending mobile:',
                '- user id:',
                '- platform:',
                'authentication rules:',
                'previous conversation context:',
                'current user message:',
                'internal context',
                'do not include'
            ]):
                skip_line = True
                continue
            
            # Skip numbered rules
            if line_lower.startswith(('1.', '2.', '3.', '4.', '5.', '6.')) and ('auth' in line_lower or 'otp' in line_lower):
                continue
                
            # Skip emoji conversation markers
            if line.startswith(('👤 ', '🤖 ')):
                continue
                
            # Reset skip if we hit a normal line
            if line.strip() and not any(marker in line_lower for marker in ['status:', 'rules:', 'context:']):
                skip_line = False
            
            if not skip_line and line.strip():
                cleaned_lines.append(line)
        
        cleaned_response = '\n'.join(cleaned_lines).strip()
        
        # If response is empty after cleaning, provide a default
        if not cleaned_response:
            return "How can I help you with municipal services today?"
        
        return cleaned_response
    
    async def _auto_authenticate_by_mobile(self, session, mobile_number: str) -> bool:
        """Auto-authenticate user by mobile number for voice calls"""
        try:
            # Clean the mobile number
            clean_mobile = mobile_number.replace('+', '').replace('-', '').replace(' ', '')
            if not clean_mobile.startswith('91') and len(clean_mobile) == 10:
                clean_mobile = '91' + clean_mobile
            
            # Try to authenticate directly (simulate OTP verification)
            # This is a special method for voice calls only
            result = await self.api_service.auto_authenticate_by_mobile(session, clean_mobile)
            
            if result.get('success'):
                session.set_authenticated(result['token'], result['user'])
                return True
            
        except Exception as e:
            print(f"❌ Auto-authentication failed: {str(e)}")
        
        return False
    
    async def _process_gemini_response(self, session, response) -> Tuple[str, List[Dict]]:
        """Process Gemini response and handle function calls"""
        
        function_calls_made = []
        
        # Check if Gemini wants to call functions
        if (response.candidates and 
            len(response.candidates) > 0 and 
            response.candidates[0].content and 
            response.candidates[0].content.parts):
            
            for part in response.candidates[0].content.parts:
                # Check if this part contains a function call
                if hasattr(part, 'function_call') and part.function_call:
                    function_name = part.function_call.name
                    function_args = dict(part.function_call.args)
                    
                    print(f"🤖 Gemini wants to call: {function_name} with args: {function_args}")
                    
                    # Execute the function
                    try:
                        result = await self._execute_function(session, function_name, **function_args)
                        print(f"✅ Function result: {json.dumps(result, indent=2)}")
                        
                        # Store function call in session history for context
                        function_call_record = {
                            "function_name": function_name,
                            "args": function_args,
                            "result": result,
                            "timestamp": datetime.now().isoformat(),
                            "result_summary": self._generate_result_summary(function_name, result)
                        }
                        session.function_call_history.append(function_call_record)
                        
                        # Keep only last 10 function calls
                        if len(session.function_call_history) > 10:
                            session.function_call_history = session.function_call_history[-10:]
                        
                        function_calls_made.append(function_call_record)
                        
                        # Handle function response
                        try:
                            # Create function response part
                            function_response_content = {
                                "result": result,
                                "success": result.get("success", True) if isinstance(result, dict) else True
                            }
                            
                            # Use the direct method to create function response
                            function_response_part = genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=function_name,
                                    response=function_response_content
                                )
                            )
                            
                            # Send function result back to Gemini
                            final_response = session.chat.send_message([function_response_part])
                            
                            # Check if there's valid text response and clean it
                            if final_response and final_response.text:
                                cleaned_response = self._clean_response_text(final_response.text)
                                return cleaned_response, function_calls_made
                            else:
                                # Fallback response generation
                                return self._generate_fallback_response(function_name, result), function_calls_made
                            
                        except Exception as gemini_error:
                            print(f"❌ Gemini processing error: {str(gemini_error)}")
                            # Generate a manual response instead of failing
                            fallback_response = self._generate_fallback_response(function_name, result)
                            return fallback_response, function_calls_made
                        
                    except Exception as e:
                        print(f"❌ Function error: {str(e)}")
                        
                        # Store error in session history
                        function_call_record = {
                            "function_name": function_name,
                            "args": function_args,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                            "result_summary": f"Error: {str(e)}"
                        }
                        session.function_call_history.append(function_call_record)
                        function_calls_made.append(function_call_record)
                        
                        # Return error response
                        return f"I encountered an error while processing your request: {str(e)}", function_calls_made
                
            # If no function calls but there's text content
            if any(hasattr(part, 'text') and part.text for part in response.candidates[0].content.parts):
                cleaned_response = self._clean_response_text(response.text)
                return cleaned_response, function_calls_made
            else:
                return "I'm not sure how to help with that. Could you please rephrase your question?", function_calls_made
        
        # If no function calls, return the direct text response (cleaned)
        elif response.text:
            cleaned_response = self._clean_response_text(response.text)
            return cleaned_response, function_calls_made
        else:
            return "I'm sorry, I didn't understand that. Could you please try again?", function_calls_made
    
    async def _execute_function(self, session, function_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a function with session context"""
        
        # Function mapping
        function_map = {
            "set_token": lambda **args: self.api_service.set_token(session, **args),
            "send_otp": lambda **args: self.api_service.send_otp(session, **args),
            "verify_otp": lambda **args: self.api_service.verify_otp(session, **args),
            "register_complaint": lambda **args: self.api_service.register_complaint(session, **args),
            "get_complaint_status": lambda **args: self.api_service.get_complaint_status(session, **args),
            "track_complaint": lambda **args: self.api_service.track_complaint(session, **args),
            "get_user_profile": lambda **args: self.api_service.get_user_profile(session, **args),
            "update_profile": lambda **args: self.api_service.update_profile(session, **args),
            "get_grievance_categories": lambda **args: self.api_service.get_grievance_categories(session, **args),
            "get_awareness_info": lambda **args: self.api_service.get_awareness_info(session, **args)
        }
        
        if function_name not in function_map:
            raise ValueError(f"Unknown function: {function_name}")
        
        return await function_map[function_name](**kwargs)
    
    def _generate_fallback_response(self, function_name: str, result: Dict[str, Any]) -> str:
        """Generate manual responses when Gemini processing fails"""
        
        if not isinstance(result, dict):
            return "Action completed successfully."
        
        success = result.get("success", True)
        
        if function_name == "send_otp":
            if success:
                mobile = result.get("mobile", "your mobile")
                return f"📱 I've sent a 6-digit OTP to {mobile}. Please tell me the code you received."
            else:
                return f"❌ I couldn't send the OTP. {result.get('error', 'Please try again with a valid mobile number.')}"
        
        elif function_name == "verify_otp":
            if success:
                user_info = result.get("user", {})
                mobile = user_info.get("mobile", "your number")
                return f"✅ Excellent! You're now logged in with {mobile}. I can help you register complaints, check complaint status, or provide information about municipal services. What would you like to do?"
            else:
                return f"❌ The OTP verification failed. {result.get('error', 'Please make sure you entered the correct 6-digit code.')}"
        
        elif function_name == "register_complaint":
            if success:
                grievance_id = result.get("grievance_id", "N/A")
                return f"✅ Your complaint has been registered successfully! Your complaint ID is *{grievance_id}*. Please note this down for future reference. You can track your complaint status anytime using this ID."
            else:
                error = result.get("error", "Unknown error")
                if "Authentication required" in error:
                    return "🔐 I need you to login first before registering complaints. Please provide your mobile number to get started."
                return f"❌ I couldn't register your complaint. {error}"
        
        elif function_name == "get_complaint_status" or function_name == "track_complaint":
            if success:
                grievance = result.get("grievance", {})
                grievance_id = grievance.get("grievance_id", "N/A")
                status = grievance.get("status", "Unknown")
                title = grievance.get("title", "N/A")
                return f"📊 Here's your complaint status:\n*Complaint ID:* {grievance_id}\n*Title:* {title}\n*Status:* {status}"
            else:
                return f"❌ I couldn't find that complaint. {result.get('error', 'Please check the complaint ID and try again.')}"
        
        elif function_name == "get_grievance_categories":
            if success:
                categories = result.get("categories", [])
                if categories:
                    category_names = [cat.get("label", cat.get("value", "Unknown")) for cat in categories[:5]]
                    category_list = ", ".join(category_names)
                    return f"📋 The main complaint categories are: {category_list}. Which category best describes your issue?"
                return "📋 I retrieved the complaint categories, but the list appears to be empty. Let me know what type of issue you're facing and I'll help categorize it."
            else:
                return f"❌ I couldn't retrieve the categories right now. {result.get('error', 'Please describe your issue and I will help you.')}"
        
        elif function_name == "get_user_profile":
            if success:
                user = result.get("user", {})
                name = user.get("name", "Not set")
                mobile = user.get("mobile", "Not set")
                return f"👤 Your profile shows:\n*Name:* {name}\n*Mobile:* {mobile}\nWould you like to update any information?"
            else:
                return f"❌ I couldn't retrieve your profile. {result.get('error', 'Please try again later.')}"
        
        else:
            if success:
                return "✅ Action completed successfully."
            else:
                return f"❌ The action failed. {result.get('error', 'Please try again.')}"
    
    def _generate_result_summary(self, function_name: str, result: Dict[str, Any]) -> str:
        """Generate a brief summary of function call results for context"""
        if not result.get("success"):
            return f"Failed: {result.get('error', 'Unknown error')}"
        
        if function_name == "register_complaint":
            return f"Registered complaint {result.get('grievance_id', 'N/A')}"
        elif function_name in ["get_complaint_status", "track_complaint"]:
            grievance = result.get("grievance", {})
            return f"Status: {grievance.get('status', 'N/A')}"
        elif function_name == "get_grievance_categories":
            categories = result.get("categories", [])
            return f"Retrieved {len(categories)} categories"
        elif function_name == "send_otp":
            return f"OTP sent to {result.get('mobile', 'N/A')}"
        elif function_name == "verify_otp":
            return "Login successful"
        elif function_name == "get_user_profile":
            user = result.get("user", {})
            return f"Profile: {user.get('name', 'N/A')}"
        else:
            return "Action completed"