"""
Intent Router

Routes WhatsApp messages to appropriate handlers based on intent classification.
Handles user registration, fund management, and all user interactions.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os
import re
from collections import namedtuple

from ai.gemini_client import GeminiClient
from services.supabase_client import SupabaseClient
from handlers.registration_handler import RegistrationHandler
from handlers.fund_handler import FundHandler
from handlers.withdrawal_handler import WithdrawalHandler
from handlers.challenge_handler import ChallengeHandler
from handlers.proof_handler import ProofHandler
from handlers.balance_handler import BalanceHandler
from handlers.reminder_handler import ReminderHandler
from handlers.help_handler import HelpHandler
from utils.logger import setup_logger

logger = setup_logger(__name__)

class IntentRouter:
    """Routes user messages to appropriate handlers."""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.gemini_client = GeminiClient()
        
        # Initialize handlers
        self.registration_handler = RegistrationHandler(supabase_client)
        self.fund_handler = FundHandler(supabase_client)
        self.withdrawal_handler = WithdrawalHandler(supabase_client)
        self.challenge_handler = ChallengeHandler(supabase_client, self.gemini_client)
        self.proof_handler = ProofHandler()
        self.balance_handler = BalanceHandler(supabase_client)
        self.reminder_handler = ReminderHandler(supabase_client, self.gemini_client)
        self.help_handler = HelpHandler()
        
        # Track conversation state for bet creation
        self.bet_conversation_state = {}
    
    async def route_message(
        self, 
        user_id: str, 
        phone_number: str, 
        message_content: str,
        message_type: str = "text",
        media_url: Optional[str] = None
    ) -> str:
        """
        Route message to appropriate intent handler using classification.
        Handles ongoing conversations and new messages.
        """
        try:
            # Skip empty messages
            if not message_content.strip() and message_type == "text":
                return None
            
            # Get user profile for balance checks
            try:
                user_profile = await self.supabase_client.get_user_profile(user_id)
                
                # If no profile, handle as unregistered user
                if not user_profile:
                    return await self._handle_unregistered_user(user_id, phone_number, message_content)
            except Exception as e:
                logger.error(f"Error fetching user profile: {e}")
                user_profile = {"balance": 0}  # Default fallback
            
            # Check if user is in an ongoing bet conversation
            if phone_number in self.bet_conversation_state:
                return await self._handle_bet_conversation(user_id, phone_number, message_content, user_profile)
                
            # Check if user is in an ongoing fund conversation
            if self.fund_handler.is_in_fund_conversation(phone_number):
                return await self.fund_handler.handle_fund_conversation(user_id, phone_number, message_content)
            
            # First try fast classification to avoid AI overhead
            intent_result = self._fast_intent_classification(message_content)
            
            # Handle the new "betting_intent" intent for "I want to bet" style messages
            if intent_result.intent == 'betting_intent':
                # Start bet conversation - ask for goal first, not amount
                self.bet_conversation_state[phone_number] = {
                    'stage': 'waiting_for_goal'
                }
                
                balance = user_profile.get("balance", 0)
                
                if balance == 0:
                    return (
                        "Hey! I'd love to help you set up a challenge 💪\n\n"
                        "But first you'll need to add some funds to get started.\n\n"
                        "Type 'add funds' to top up your wallet!"
                    )
                
                return (
                    "Nice! Let's set up a challenge 🎯\n\n"
                    "What do you want to bet on? Just tell me your goal, like:\n"
                    "• 'Go to gym today'\n"
                    "• 'Study for 2 hours'\n"
                    "• 'Wake up at 6am tomorrow'\n\n"
                    f"💰 Balance: ₹{balance}"
                )
            
            # If we have a strong match, skip AI classification
            if intent_result.confidence >= 0.8:
                return await self._route_by_intent(
                    intent_result, user_id, phone_number, message_content, user_profile
                )
                
            # For unknown or low confidence intents, use AI classification
            try:
                # Use Gemini to classify more complex intents
                gemini_client = GeminiClient()
                ai_intent = await gemini_client.classify_intent(message_content)
                
                if ai_intent:
                    logger.info(f"AI classified intent: {ai_intent}")
                    
                    # Handle different response formats
                    if hasattr(ai_intent, 'intent'):
                        # It's already an object with the right attributes
                        return await self._route_by_intent(
                            ai_intent, user_id, phone_number, message_content, user_profile
                        )
                    else:
                        # It's a dict or something else, create an object
                        intent_obj = type('obj', (object,), {
                            'intent': ai_intent.get('intent', 'unknown') if isinstance(ai_intent, dict) else 'unknown',
                            'confidence': ai_intent.get('confidence', 0.5) if isinstance(ai_intent, dict) else 0.5,
                            'extracted_data': ai_intent.get('extracted_data', {}) if isinstance(ai_intent, dict) else {}
                        })()
                        
                        return await self._route_by_intent(
                            intent_obj, user_id, phone_number, message_content, user_profile
                        )
            except Exception as e:
                logger.error(f"Error using AI classification: {e}")
                # Continue to fallback
            
            # Fallback to help message for completely unknown intents
            try:
                # Try to use AI for conversational response for unknown intents too
                response = await self.gemini_client.generate_conversational_response(
                    message=message_content,
                    user_context=user_profile,
                    conversation_history=None
                )
                return response
            except Exception as e:
                logger.error(f"Error generating fallback conversational response: {e}")
                # Final fallback - friendly but helpful
                balance = user_profile.get("balance", 0)
                
                # Be more encouraging about goal setting
                if balance > 0:
                    return "Hmm, not sure what you mean! 🤔 Just tell me what you want to work on and I'll help set it up as a challenge! Like 'gym today' or 'study for 1 hour' 💪"
                else:
                    return "Hey! 👋 I help people achieve goals by betting money on them. Type 'add funds' to get started, then tell me what you want to work on! 🎯"
                
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            return "Oops! 😅 Something went wrong on my end. Could you try again? If it keeps happening, just type 'help' and I'll get you sorted! 💪"
    
    async def _handle_bet_conversation(self, user_id: str, phone_number: str, message: str, user_profile: Dict[str, Any]) -> str:
        """Handle ongoing bet conversation state with improved natural language understanding."""
        state = self.bet_conversation_state[phone_number]
        
        # First check if user wants to escape/cancel
        intent_result = self._fast_intent_classification(message)
        
        if intent_result.intent in ['list_challenges', 'get_balance', 'help', 'cancel_conversation']:
            # Clear conversation state and route to the intended handler
            del self.bet_conversation_state[phone_number]
            return await self._route_by_intent(
                intent_result, user_id, phone_number, message, user_profile
            )
        
        # Handle goal setting stage
        if state.get('stage') == 'waiting_for_goal' or ('goal' not in state and 'amount' not in state):
            # IMPROVED: Handle "no bet rs 10 and change goal" patterns
            if 'no' in message.lower() and ('bet' in message.lower() or 'rs' in message.lower() or '₹' in message.lower()) and 'change' in message.lower():
                # Extract amount from "rs 10" or "₹10" patterns
                amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message.lower())
                if amount_match:
                    amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
                    state['amount'] = amount
                    state['stage'] = 'waiting_for_goal'
                    
                    return (
                        f"Got it! ₹{amount} it is! 💰\n\n"
                        f"What's your new goal? Like:\n"
                        f"• 'Go to gym today'\n"
                        f"• 'Study for 2 hours'\n"
                        f"• 'Complete project work'"
                    )
                else:
                    return (
                        "I see you want to change things! 🔄\n\n"
                        "What's your new goal and how much do you want to bet?\n"
                        "Example: 'Go to gym today, bet ₹50'"
                    )
            
            # If user is trying to provide an amount before the goal, extract both
            # IMPROVED: Use better regex that doesn't match time references
            amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message.lower())
            if amount_match:
                amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
                # Save amount but still ask for a proper goal
                state['amount'] = amount
                
                # Remove amount part to extract goal text - be more careful
                goal_text = re.sub(r'₹\d+|\brs\s*\d+|\b\d+\s*rs\b|\b\d+\s*rupees?\b', '', message, flags=re.IGNORECASE).strip()
                # Clean up the goal text
                clean_goal = self._extract_clean_goal(goal_text)
                
                # Check if it's a setup request rather than actual goal
                setup_indicators = ['set a challenge', 'create a challenge', 'make a challenge', 'for till', 'o\'clock', 'time']
                is_setup_request = any(indicator in clean_goal.lower() for indicator in setup_indicators)
                
                if len(clean_goal) > 2 and not is_setup_request:  # If there's a reasonable goal text
                    state['goal'] = clean_goal
                    state['stage'] = 'asking_recurring_type'
                    
                    return (
                        f"Perfect! ₹{amount} bet on '{clean_goal}' 💪\n\n"
                        f"One more thing: Do you want this to be:\n\n"
                        f"📋 **One-time** - Just today\n"
                        f"🔄 **Recurring** - Repeat daily/weekly\n\n"
                        f"Reply 'one-time' or 'recurring'"
                    )
                else:
                    # We have amount but need goal
                    state['stage'] = 'waiting_for_goal'
                    return (
                        f"Cool, ₹{amount} it is! 💰\n\n"
                        f"What's your actual goal though? Like:\n"
                        f"• 'Go to gym'\n"
                        f"• 'Study for 2 hours'\n"
                        f"• 'Complete project work'"
                    )
            
            # User provided a goal without amount
            clean_goal = self._extract_clean_goal(message)
            
            # Check if it's a setup request - redirect to proper goal asking
            setup_indicators = ['set a challenge', 'create a challenge', 'make a challenge', 'for till', 'o\'clock', 'time']
            is_setup_request = any(indicator in clean_goal.lower() for indicator in setup_indicators)
            
            if is_setup_request:
                return (
                    "I understand you want to set up a challenge! 🎯\n\n"
                    "But I need to know what specific activity you want to work on.\n\n"
                    "What's your goal? Like:\n"
                    "• 'Go to gym'\n"
                    "• 'Study for 2 hours'\n"
                    "• 'Complete a project'\n"
                    "• 'Read 20 pages'"
                )
            
            state['goal'] = clean_goal
            state['stage'] = 'waiting_for_amount'
            
            balance = user_profile.get("balance", 0)
            return (
                f"Nice goal! '{clean_goal}' 🎯\n\n"
                f"How much you thinking? You've got ₹{balance} to work with 💰"
            )
        
        # If user says "recurring" at any point, handle frequency (but not if already waiting for frequency)
        if (message.lower().strip() in ['recurring', 'repeat'] or 
            (message.lower().strip() in ['daily', 'weekly'] and state.get('stage') != 'waiting_for_frequency')):
            state['task_type'] = 'recurring'
            state['stage'] = 'waiting_for_frequency'
            
            # If we already have a goal, show it
            goal_text = state.get('goal', 'your goal')
            
            return (
                f"Ooh recurring! I like it 🔄\n\n"
                f"Goal: '{goal_text}'\n\n"
                f"How often? Daily, weekly, or something else?"
            )
        
        # Handle frequency selection
        if state.get('stage') == 'waiting_for_frequency':
            frequency_map = {
                'daily': 'daily',
                'weekly': 'weekly', 
                'twice a week': 'twice_weekly',
                '2 times per week': 'twice_weekly',
                '3 times per week': 'thrice_weekly',
                'thrice a week': 'thrice_weekly',
                'daily except sunday': 'daily_except_sunday',
                'every day except sunday': 'daily_except_sunday',
                'everyday except sunday': 'daily_except_sunday'
            }
            
            freq_input = message.lower().strip()
            
            # Check for custom patterns first
            if 'except sunday' in freq_input or 'except sun' in freq_input:
                frequency = 'daily_except_sunday'
                frequency_display = 'daily except Sunday'
            else:
                frequency = frequency_map.get(freq_input, 'daily')  # Default to daily
                frequency_display = frequency.replace('_', ' ')
            
            state['recurring_frequency'] = frequency
            
            # If we already have amount, go to confirmation
            if 'amount' in state:
                state['stage'] = 'waiting_for_confirmation'
                goal_text = state.get('goal', 'your goal')
                amount = state['amount']
                
                return (
                    f"Perfect! Here's what we've got:\n\n"
                    f"🎯 {goal_text}\n"
                    f"📅 {frequency_display.capitalize()}\n"
                    f"💰 ₹{amount} bet each time\n\n"
                    f"Ready to do this? Say 'yes'!"
                )
            else:
                # Need amount
                state['stage'] = 'waiting_for_amount'
                balance = user_profile.get("balance", 0)
                
                return (
                    f"Sweet, {frequency_display} it is! 📅\n\n"
                    f"How much you want to bet each time? (You've got ₹{balance})"
                )
        
        # Handle amount stage
        if state.get('stage') == 'waiting_for_amount':
            balance = user_profile.get("balance", 0)
            
            # Check if user is trying to clarify the goal instead of providing amount
            if not re.search(r'\d+', message) and len(message.split()) <= 3:
                # User might be clarifying the goal (like "water" for "drinking water")
                current_goal = state.get('goal', '')
                
                # Try to improve the goal with the clarification
                if 'water' in message.lower() and 'water' in current_goal.lower():
                    # User clarified "water" - keep current goal
                    return f"Got it! '{current_goal}' 💧\n\nHow much you want to bet? You've got ₹{balance} to work with"
                elif len(message) > 1:
                    # Update goal with user's clarification
                    state['goal'] = message
                    return f"Perfect! '{message}' 🎯\n\nHow much you want to bet? (₹{balance} available)"
            
            # Handle "bet all" or similar natural language
            if intent_result.intent == 'bet_amount_all':
                if balance <= 0:
                    return (
                        f"Whoa! You don't have any money to bet! 😅\n\n"
                        f"Type 'add funds' to get started 💰"
                    )
                amount = int(balance)  # Bet all available balance
                
            elif intent_result.intent == 'bet_amount':
                amount = intent_result.extracted_data.get('amount', 0)
                
            else:
                # Try to extract amount from message
                amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message.lower())
                if amount_match:
                    amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
                else:
                    return (
                        f"Hmm, not sure what amount you mean 🤔\n\n"
                        f"Just tell me a number like '100' or '200'"
                    )
            
            if amount > balance:
                return (
                    f"Oops! That's more than you have 😬\n\n"
                    f"You want ₹{amount} but only have ₹{balance}\n\n"
                    f"Try a smaller amount or say 'all' to bet everything!"
                )
            
            if amount <= 0:
                return (
                    f"Come on, you gotta bet at least ₹1! 😄\n\n"
                    f"What amount feels right?"
                )
            
            # Save amount and move to recurring choice instead of confirmation
            state['amount'] = amount
            state['stage'] = 'asking_recurring_type'
            
            goal_text = state.get('goal', 'your goal')
            
            return (
                f"Perfect! ₹{amount} bet on '{goal_text}' 💪\n\n"
                f"One more thing: Do you want this to be:\n\n"
                f"📋 **One-time** - Just today\n"
                f"🔄 **Recurring** - Repeat daily/weekly\n\n"
                f"Reply 'one-time' or 'recurring'"
            )
        
        # Handle recurring type choice
        if state.get('stage') == 'asking_recurring_type':
            if message.lower().strip() in ['one-time', 'onetime', 'one time', 'once', 'just today', 'today only']:
                state['task_type'] = 'one-time'
                state['stage'] = 'waiting_for_confirmation'
                
                goal_text = state.get('goal', 'your goal')
                amount = state.get('amount', 0)
                
                return (
                    f"Got it! One-time challenge:\n\n"
                    f"🎯 {goal_text}\n"
                    f"📋 Type: One-time\n"
                    f"💰 ₹{amount} bet\n\n"
                    f"Ready to do this? Say 'yes'! 🚀"
                )
            
            elif message.lower().strip() in ['recurring', 'repeat', 'daily', 'weekly', 'multiple times']:
                state['task_type'] = 'recurring'
                state['stage'] = 'waiting_for_frequency'
                
                goal_text = state.get('goal', 'your goal')
                
                return (
                    f"Awesome! Recurring challenge 🔄\n\n"
                    f"Goal: '{goal_text}'\n\n"
                    f"How often?\n"
                    f"• 'daily' - Every day\n"
                    f"• 'weekly' - Once a week\n"
                    f"• '3 times per week'\n"
                    f"• 'daily except sunday'"
                )
            else:
                # Try to understand their intent
                if 'daily' in message.lower() or 'every day' in message.lower():
                    state['task_type'] = 'recurring'
                    state['recurring_frequency'] = 'daily'
                    state['stage'] = 'waiting_for_confirmation'
                    
                    goal_text = state.get('goal', 'your goal')
                    amount = state.get('amount', 0)
                    
                    return (
                        f"Perfect! Daily recurring challenge:\n\n"
                        f"🎯 {goal_text}\n"
                        f"📅 Every day\n"
                        f"💰 ₹{amount} bet daily\n\n"
                        f"Ready to commit? Say 'yes'! 💪"
                    )
                else:
                    return (
                        f"🤔 Not sure what you mean.\n\n"
                        f"Please choose:\n"
                        f"• 'one-time' - Just for today\n"
                        f"• 'recurring' - Repeat regularly"
                    )
        
        # Handle confirmation stage
        if state.get('stage') == 'waiting_for_confirmation':
            if message.lower() in ['yes', 'y', 'yeah', 'yep', 'confirm', 'ok', 'okay', 'sure', 'create']:
                # Create the challenge
                try:
                    balance = user_profile.get("balance", 0)
                    challenge_title = state.get('goal', 'My challenge')
                    amount = state.get('amount', 100)
                    task_type = state.get('task_type', 'one-time')
                    
                    # Create challenge
                    deadline = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
                    
                    challenge_data = {
                        "user_id": user_id,
                        "title": challenge_title,
                        "description": challenge_title,
                        "task_type": task_type,
                        "amount": amount,
                        "deadline": deadline.isoformat(),
                        "verification_method": "photo",
                        "verification_details": "Submit clear proof of completion",
                        "status": "active"
                    }
                    
                    # Add recurring fields if needed
                    if task_type == 'recurring':
                        challenge_data["recurring_frequency"] = state.get('recurring_frequency', 'daily')
                        challenge_data["recurring_duration"] = "1month"  # Fixed: use valid constraint value
                    
                    result = self.supabase_client.client.table("challenges").insert(challenge_data).execute()
                    
                    if result.data:
                        # Deduct amount from balance
                        new_balance = balance - amount
                        await self.supabase_client.update_user_balance(user_id, new_balance)
                        
                        # Record transaction
                        await self.supabase_client.record_transaction(
                            user_id=user_id,
                            amount=-amount,
                            transaction_type="deduction",
                            description=f"Challenge bet: {challenge_title}",
                            challenge_id=result.data[0]["id"]
                        )
                        
                        # Clear conversation state
                        del self.bet_conversation_state[phone_number]
                        
                        # Format type info
                        type_text = "One-time"
                        if task_type == "recurring":
                            frequency = state.get('recurring_frequency', 'daily')
                            if frequency == 'daily_except_sunday':
                                type_text = "Daily except Sunday"
                            else:
                                type_text = frequency.replace('_', ' ').capitalize()
                        
                        # Add appropriate deadline text for recurring
                        if task_type == "recurring":
                            deadline_text = f"⏰ Next deadline: {deadline.strftime('%b %d, %I:%M %p')}"
                            type_info = f"📋 Type: {type_text} (recurring)\n💰 Bet: ₹{amount} each time"
                        else:
                            deadline_text = f"⏰ Deadline: {deadline.strftime('%b %d, %I:%M %p')}"
                            type_info = f"📋 Type: {type_text}\n💰 Bet: ₹{amount}"
                        
                        return (
                            f"✅ Challenge Created!\n\n"
                            f"🎯 {challenge_title}\n"
                            f"{type_info}\n"
                            f"{deadline_text}\n\n"
                            f"💡 Submit proof at:\n"
                            f"🌐 dare-you-succeed.vercel.app\n\n"
                            f"New balance: ₹{new_balance}"
                        )
                    else:
                        return "❌ Error creating challenge. Please try again."
                        
                except Exception as e:
                    logger.error(f"Error creating challenge: {e}")
                    return "❌ Error creating challenge. Please try again."
            
            elif message.lower() in ['edit', 'change', 'modify', 'no']:
                # Ask what they want to edit
                return (
                    f"What would you like to change?\n\n"
                    f"• 'goal' - Change the challenge description\n"
                    f"• 'amount' - Change the bet amount\n"
                    f"• 'type' - Change between one-time/recurring\n\n"
                    f"Or type 'cancel' to start over."
                )
            
            # IMPROVED: Handle complex modification patterns like "no bet rs 10 and change goal"
            elif 'no' in message.lower() and ('bet' in message.lower() or 'rs' in message.lower() or '₹' in message.lower()):
                # User wants to modify both amount and goal
                amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message.lower())
                
                if amount_match:
                    amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
                    state['amount'] = amount
                    
                    if 'change' in message.lower() and ('goal' in message.lower() or 'gaol' in message.lower()):
                        # User wants to change goal too
                        state['stage'] = 'edit_goal'
                        return (
                            f"Got it! Updated amount to ₹{amount} 💰\n\n"
                            f"Now what's your new goal? Like:\n"
                            f"• 'Go to gym today'\n"
                            f"• 'Study for 2 hours'\n"
                            f"• 'Complete project work'"
                        )
                    else:
                        # Just amount change
                        balance = user_profile.get("balance", 0)
                        if amount > balance:
                            return (
                                f"❌ That's more than your balance!\n\n"
                                f"💰 You want: ₹{amount}\n"
                                f"💳 You have: ₹{balance}\n\n"
                                f"Try a smaller amount."
                            )
                        
                        goal_text = state.get('goal', 'your goal')
                        task_type = state.get('task_type', 'one-time')
                        
                        return (
                            f"📋 Updated Challenge:\n"
                            f"• Goal: {goal_text}\n"
                            f"• Type: {task_type.replace('_', ' ').title()}\n"
                            f"• Bet: ₹{amount}\n\n"
                            f"Reply 'yes' to create this challenge!"
                        )
                else:
                    return (
                        "I see you want to make changes! 🔄\n\n"
                        "What would you like to modify?\n"
                        "• Amount: Just tell me the new amount\n"
                        "• Goal: Type 'change goal' and then your new goal"
                    )
            
            elif 'goal' in message.lower() or 'description' in message.lower():
                # Edit goal
                state['stage'] = 'edit_goal'
                return "What's your new goal description?"
            
            elif 'amount' in message.lower() or 'bet' in message.lower() or 'money' in message.lower():
                # Edit amount
                state['stage'] = 'waiting_for_amount'
                balance = user_profile.get("balance", 0)
                return (
                    f"💰 What amount would you like to bet instead?\n"
                    f"💳 Your balance: ₹{balance}\n\n"
                    f"Reply with a number like '100' or '₹200'."
                )
            
            elif 'type' in message.lower() or 'recurring' in message.lower() or 'frequency' in message.lower():
                # Edit type
                if state.get('task_type') == 'recurring':
                    # Change to one-time
                    state['task_type'] = 'one-time'
                    if 'recurring_frequency' in state:
                        del state['recurring_frequency']
                    state['stage'] = 'waiting_for_confirmation'
                    
                    return (
                        f"📋 Updated to One-time challenge:\n"
                        f"• Goal: {state.get('goal', 'your goal')}\n"
                        f"• Type: One-time\n"
                        f"• Bet: ₹{state.get('amount', 0)}\n\n"
                        f"Reply 'yes' to create or 'edit' to change something else."
                    )
                else:
                    # Change to recurring
                    state['task_type'] = 'recurring'
                    state['stage'] = 'waiting_for_frequency'
                    
                    return (
                        f"📅 Changing to recurring challenge!\n\n"
                        f"How often?\n"
                        f"• 'daily' - Every day\n"
                        f"• 'weekly' - Once a week\n"
                        f"• '3 times per week'\n"
                        f"• 'daily except sunday'"
                    )
            
            # Handle amounts or goals sent directly during confirmation
            amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message.lower())
            if amount_match:
                amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
                balance = user_profile.get("balance", 0)
                
                if amount > balance:
                    return (
                        f"❌ That's more than your balance!\n\n"
                        f"💰 You want to bet: ₹{amount}\n"
                        f"💳 Your balance: ₹{balance}\n\n"
                        f"Please enter a smaller amount."
                    )
                
                # Update amount
                state['amount'] = amount
                
                goal_text = state.get('goal', 'your goal')
                task_type = state.get('task_type', 'one-time')
                frequency = state.get('recurring_frequency', 'daily' if task_type == 'recurring' else None)
                
                if task_type == 'recurring':
                    return (
                        f"📋 Updated Challenge Summary:\n"
                        f"• Goal: {goal_text}\n"
                        f"• Type: {frequency.replace('_', ' ')}\n"
                        f"• Bet: ₹{amount}\n\n"
                        f"Reply 'yes' to create this challenge, or 'edit' to change something else."
                    )
                else:
                    return (
                        f"📋 Updated Challenge Summary:\n"
                        f"• Goal: {goal_text}\n"
                        f"• Type: One-time\n"
                        f"• Bet: ₹{amount}\n\n"
                        f"Reply 'yes' to create this challenge, or 'edit' to change something else."
                    )
            
            # If message is long enough, treat as new goal
            if len(message) > 5:
                state['goal'] = message
                
                amount = state.get('amount', 0)
                task_type = state.get('task_type', 'one-time')
                frequency = state.get('recurring_frequency', 'daily' if task_type == 'recurring' else None)
                
                if task_type == 'recurring':
                    return (
                        f"📋 Updated Challenge Summary:\n"
                        f"• Goal: {message}\n"
                        f"• Type: {frequency.replace('_', ' ')}\n"
                        f"• Bet: ₹{amount}\n\n"
                        f"Reply 'yes' to create this challenge, or 'edit' to change something else."
                    )
                else:
                    return (
                        f"📋 Updated Challenge Summary:\n"
                        f"• Goal: {message}\n"
                        f"• Type: One-time\n"
                        f"• Bet: ₹{amount}\n\n"
                        f"Reply 'yes' to create this challenge, or 'edit' to change something else."
                    )
        
        # Handle edit goal stage
        if state.get('stage') == 'edit_goal':
            state['goal'] = message
            state['stage'] = 'waiting_for_confirmation'
            
            amount = state.get('amount', 0)
            task_type = state.get('task_type', 'one-time')
            frequency = state.get('recurring_frequency', 'daily' if task_type == 'recurring' else None)
            
            if task_type == 'recurring':
                return (
                    f"📋 Updated Challenge Summary:\n"
                    f"• Goal: {message}\n"
                    f"• Type: {frequency.replace('_', ' ')}\n"
                    f"• Bet: ₹{amount}\n\n"
                    f"Reply 'yes' to create this challenge, or 'edit' to change something else."
                )
            else:
                return (
                    f"📋 Updated Challenge Summary:\n"
                    f"• Goal: {message}\n"
                    f"• Type: One-time\n"
                    f"• Bet: ₹{amount}\n\n"
                    f"Reply 'yes' to create this challenge, or 'edit' to change something else."
                )
        
        # Fallback - reset conversation
        del self.bet_conversation_state[phone_number]
        return "❌ I got confused with the challenge creation. Let's start over. What goal would you like to bet on?"
    
    def _fast_intent_classification(self, message: str):
        """
        Fast intent classification without using Gemini.
        Returns an IntentResult object with the detected intent and extracted data.
        """
        IntentResult = namedtuple('IntentResult', ['intent', 'confidence', 'extracted_data'])
        message_lower = message.lower().strip()
        extracted_data = {}
        
        # Help intent - highest priority
        if message_lower in ['help', 'help me', 'commands', 'what can you do', 'menu', 'instructions', '?']:
            return IntentResult('help', 0.95, {})
        
        # Cancel intent
        if message_lower in ['cancel', 'stop', 'exit', 'quit', 'abort', 'nevermind', 'never mind', 'cancel conversation']:
            return IntentResult('cancel_conversation', 0.95, {})
        
        # PRIORITY: Detect recent challenge modifications
        recent_challenge_modification_patterns = [
            'can you make this recurring', 'make this recurring', 'change this to recurring',
            'make it recurring', 'change it to recurring', 'this should be recurring',
            'can you change this to recurring', 'make this repeat', 'make it repeat',
            'make this daily', 'make it daily', 'make this weekly', 'make it weekly',
            'can i make this recurring', 'can i change this', 'can i edit this',
            'change this challenge', 'edit this challenge', 'modify this challenge',
            'update this challenge', 'make this a recurring', 'turn this into recurring'
        ]
        
        # Check if user is referring to "this" challenge with modification intent
        if any(pattern in message_lower for pattern in recent_challenge_modification_patterns):
            # Extract modification details
            if 'recurring' in message_lower:
                extracted_data['modification_type'] = 'make_recurring'
                # Extract frequency if mentioned
                if 'daily' in message_lower or 'every day' in message_lower:
                    extracted_data['frequency'] = 'daily'
                elif 'weekly' in message_lower or 'every week' in message_lower:
                    extracted_data['frequency'] = 'weekly'
                elif 'except sunday' in message_lower:
                    extracted_data['frequency'] = 'daily_except_sunday'
                    extracted_data['special_frequency'] = 'every day except Sunday'
            return IntentResult('modify_recent_challenge', 0.95, extracted_data)
        
        # Edit intent - check for edit patterns BEFORE challenge creation
        if any(pattern in message_lower for pattern in ['edit', 'modify', 'change', 'update', 'alter']):
            # Check if it's about editing a challenge
            if any(word in message_lower for word in ['challenge', 'bet', 'goal']):
                return IntentResult('edit_challenge', 0.9, {})
        
        # Balance intent
        if message_lower in ['balance', 'wallet', 'check balance', 'my balance', 'my wallet', 'money', 'how much money', 'funds', 'check wallet', 'account']:
            return IntentResult('get_balance', 0.95, {})
        
        # Transaction history intent
        if any(pattern in message_lower for pattern in ['history', 'transactions', 'transaction history', 'payment history', 'my transactions', 'past transactions']):
            return IntentResult('transaction_history', 0.95, {})
            
        # List challenges intent - moved up for better priority
        if any(pattern in message_lower for pattern in ['my challenges', 'list challenges', 'show challenges', 'view challenges', 'challenges', 'my bets', 'active challenges', 'show my challenges']):
            return IntentResult('list_challenges', 0.95, {})
            
        # Add funds intent
        if any(pattern in message_lower for pattern in ['add funds', 'deposit', 'add money', 'put money', 'fund', 'recharge']):
            return IntentResult('add_funds', 0.95, {})
        
        # Information/Help requests - check BEFORE challenge creation  
        info_patterns = [
            'how to', 'how do i', 'how can i', 'what is', 'where to', 'where do i',
            'explain', 'tell me about', 'info about', 'information', 'guide'
        ]
        if any(pattern in message_lower for pattern in info_patterns):
            return IntentResult('information_request', 0.9, {})
        
        # Completion/Verification intents - check BEFORE challenge creation but after info requests
        completion_patterns = [
            'i completed', 'i finished', 'i did', 'i studied', 'i went to', 'i exercised', 
            'i worked out', 'i read', 'done', 'completed', 'finished', 'submit proof',
            'verify my challenge', 'verification', 'submit my proof'
        ]
        if any(pattern in message_lower for pattern in completion_patterns):
            return IntentResult('completion_or_verification', 0.9, {})
        
        # Check for explicit "create challenge" commands - HANDLE THIS FIRST
        create_challenge_commands = [
            'create challenge', 'new challenge', 'make challenge', 'start challenge',
            'i want you to create challenge', 'i want to create challenge', 'make bet',
            'create bet', 'new bet', 'start bet', 'i want to set a challenge'
        ]
        if any(command in message_lower for command in create_challenge_commands):
            return IntentResult('betting_intent', 0.95, {})
        
        # Check for "I want to bet" FIRST before other patterns
        betting_intent_patterns = [
            'i want to bet', 'i would like to bet', 'i wanna bet', 'let me bet', 
            'i wish to bet', "i'd like to bet", 'can i bet', 'i want bet'
        ]
        if any(pattern in message_lower for pattern in betting_intent_patterns):
            return IntentResult('betting_intent', 0.95, {})
        
        # MUCH MORE GENEROUS goal/task detection patterns - moved BEFORE other checks
        goal_action_words = [
            # Exercise/Health
            'gym', 'workout', 'exercise', 'run', 'jog', 'walk', 'swim', 'cycling', 'yoga', 'fitness',
            'push ups', 'sit ups', 'cardio', 'weights', 'sports', 'basketball', 'football', 'tennis',
            
            # Learning/Work
            'study', 'read', 'learn', 'book', 'course', 'homework', 'assignment', 'project', 'work',
            'practice', 'coding', 'programming', 'writing', 'research', 'meeting', 'presentation',
            
            # Personal Development
            'meditate', 'meditation', 'journal', 'diary', 'reflect', 'plan', 'organize', 'schedule',
            
            # Health/Lifestyle
            'sleep', 'wake up', 'wake', 'early', 'bed', 'diet', 'eat', 'cook', 'meal', 'food',
            'drink water', 'vitamin', 'medicine', 'doctor', 'dentist',
            
            # Productivity/Chores
            'clean', 'organize', 'tidy', 'laundry', 'dishes', 'shopping', 'groceries', 'call',
            'email', 'reply', 'finish', 'complete', 'start', 'begin',
            
            # Skills/Hobbies  
            'guitar', 'piano', 'music', 'singing', 'drawing', 'painting', 'art', 'photography',
            'language', 'spanish', 'french', 'german', 'japanese'
        ]
        
        # Goal-oriented phrases that indicate task creation
        goal_phrases = [
            'i want to', 'i need to', 'i should', 'i will', 'i am going to', 'i\'m going to',
            'want to', 'need to', 'should', 'will', 'going to', 'gonna', 'planning to',
            'have to', 'gotta', 'must', 'trying to', 'working on', 'time to'
        ]
        
        # Time indicators often used with goals
        time_words = ['today', 'tomorrow', 'tonight', 'morning', 'evening', 'daily', 'week', 'hour', 'minutes']
        
        # Check for any goal-related content
        has_goal_action = any(word in message_lower for word in goal_action_words)
        has_goal_phrase = any(phrase in message_lower for phrase in goal_phrases)
        has_time_word = any(word in message_lower for word in time_words)
        
        # IMPROVED: Don't treat setup/configuration requests as challenge creation
        setup_patterns = [
            'set a challenge', 'create a challenge', 'make a challenge', 'want to set a challenge',
            'need to set a challenge', 'set up a challenge', 'configure a challenge'
        ]
        
        is_setup_request = any(pattern in message_lower for pattern in setup_patterns)
        
        # If it's a setup request, redirect to betting_intent
        if is_setup_request:
            return IntentResult('betting_intent', 0.95, {})
        
        # If message contains goal-related content AND has specific activities, lean heavily towards task creation
        # BUT exclude setup/configuration requests
        if has_goal_action and not is_setup_request:
            extracted_data['goal'] = message
            
            # IMPROVED: Don't extract amounts from time references
            # Check for amount mentioned, but exclude time patterns
            amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message_lower)
            if amount_match:
                # Extract the actual amount from the matched groups
                amount_text = amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4)
                extracted_data['amount'] = int(amount_text)
            
            return IntentResult('create_challenge_intent', 0.9, extracted_data)
        
        # If it has goal phrases but no specific activities, be more cautious
        elif has_goal_phrase and not is_setup_request:
            # Only if it also mentions specific activities
            if has_goal_action:
                extracted_data['goal'] = message
                return IntentResult('create_challenge_intent', 0.8, extracted_data)
            else:
                # Might be a general request, be more conservative
                return IntentResult('create_challenge_intent', 0.6, extracted_data)
        
        # Simple "bet" without context
        if message_lower in ['bet', 'betting', 'i bet', 'lets bet', "let's bet"]:
            return IntentResult('betting_intent', 0.9, {})
        
        # Bet creation patterns - check for "bet all" first
        if any(pattern in message_lower for pattern in ['bet all', 'all in', 'bet my entire balance', 'bet everything', 'bet full balance', 'let\'s bet all', 'stake all']):
            # Extract if a goal is also included
            if 'on' in message_lower:
                # Extract goal after "on"
                goal_parts = message_lower.split('on', 1)
                if len(goal_parts) > 1 and len(goal_parts[1].strip()) > 3:
                    extracted_data['challenge_text'] = goal_parts[1].strip()
            return IntentResult('bet_amount_all', 0.95, extracted_data)
        
        # Check for amount followed by goal (but not if it starts with edit/modify words)
        amount_match = re.search(r'₹(\d+)|\brs\s*(\d+)|\b(\d+)\s*rs\b|\b(\d+)\s*rupees?\b', message_lower)
        bet_intent = any(keyword in message_lower for keyword in ['bet', 'betting', 'wager', 'stake', 'challenge', 'let\'s bet', 'i bet', 'i want to bet'])
        
        if amount_match and bet_intent and not any(edit_word in message_lower for edit_word in ['edit', 'modify', 'change', 'update', 'alter']):
            amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
            extracted_data['amount'] = amount
            
            # Extract goal from message by removing amount and betting words
            goal_text = re.sub(r'₹\d+|\brs\s*\d+|\b\d+\s*rs\b|\b\d+\s*rupees?\b', '', message, flags=re.IGNORECASE).strip()
            for keyword in ['bet', 'betting', 'wager', 'stake', 'challenge', 'let\'s bet', 'i bet', 'i want to bet']:
                goal_text = re.sub(r'(?i)\b' + keyword + r'\b', '', goal_text).strip()
            
            # Clean up common bet patterns
            goal_text = re.sub(r'(?i)^(i will|i want to|i would like to|i am going to|i plan to|i\'m going to)', '', goal_text).strip()
            
            # If we have a reasonable goal text, include it
            if len(goal_text) > 3:
                extracted_data['challenge_text'] = goal_text
                return IntentResult('create_challenge_with_amount', 0.85, extracted_data)
            else:
                return IntentResult('bet_amount', 0.85, extracted_data)
        
        # Just amount (common user response pattern) - but not if it's an edit context
        if amount_match and len(message_lower) < 10 and not any(edit_word in message_lower for edit_word in ['edit', 'modify', 'change']):
            amount = int(amount_match.group(1) or amount_match.group(2) or amount_match.group(3) or amount_match.group(4))
            extracted_data['amount'] = amount
            return IntentResult('bet_amount', 0.8, extracted_data)
        
        # Challenge creation - MUCH MORE RESTRICTIVE now
        # Only match CLEAR commitment patterns with future tense or explicit challenge language
        challenge_creation_patterns = [
            'i will', 'i am going to', "i'm going to", 'i plan to', 'i want to',
            'i would like to', 'i intend to', 'my goal is to'
        ]
        
        # Must have one of these patterns AND not be completion/info request
        has_challenge_pattern = any(pattern in message_lower for pattern in challenge_creation_patterns)
        
        # Exclude if it's clearly not a challenge creation
        exclusion_patterns = [
            'i studied', 'i completed', 'i finished', 'i did', 'i went', 'i exercised',
            'i worked out', 'i read', 'how to', 'how do i', 'where to', 'verify',
            'submit', 'proof', 'done', 'completed', 'finished', 'create challenge',
            'new challenge', 'make challenge', 'start challenge', 'i want you to create',
            'make this recurring', 'make it recurring', 'change this', 'edit this'  # Exclude recent challenge modification
        ]
        has_exclusion = any(pattern in message_lower for pattern in exclusion_patterns)
        
        if (has_challenge_pattern and 
            not has_exclusion and
            not any(edit_word in message_lower for edit_word in ['edit', 'modify', 'change', 'update', 'alter']) and
            not any(betting_word in message_lower for betting_word in ['i want to bet', 'i would like to bet', 'i want bet'])):
            
            # Extract the challenge text
            challenge_text = message
            
            # Remove common prefixes to get cleaner goal text
            challenge_text = re.sub(r'(?i)^(i will|i want to|i would like to|i am going to|i plan to|i\'m going to|create challenge:|my goal is|new challenge:)', '', challenge_text).strip()
            
            extracted_data['challenge_text'] = challenge_text
            return IntentResult('create_challenge_intent', 0.8, extracted_data)
        
        # Even if no clear patterns, if the message sounds like someone stating what they want to do,
        # lean towards task creation rather than general chat
        if len(message.split()) >= 2:  # More than just one word
            return IntentResult('create_challenge_intent', 0.6, extracted_data)
        
        # Handle single-word goals/clarifications that might be activities
        single_word_activities = [
            'water', 'gym', 'study', 'read', 'exercise', 'run', 'walk', 'swim', 'yoga',
            'meditate', 'sleep', 'cook', 'clean', 'work', 'write', 'practice'
        ]
        
        if message_lower in single_word_activities:
            extracted_data['goal'] = message
            return IntentResult('create_challenge_intent', 0.7, extracted_data)
        
        # Simple greetings and casual chat
        simple_greetings = ["hi", "hello", "hey", "thanks", "thank you", "bye", "good morning", "good evening"]
        if any(greeting in message_lower for greeting in simple_greetings):
            # Only classify as general_chat if it's a short greeting without goal words
            words = message.split()
            if len(words) <= 3 and not has_goal_action and not has_goal_phrase:
                return IntentResult('general_chat', 0.8, {})
        
        # Default fallback - unrecognized intent
        return IntentResult('unknown', 0.5, {})
    
    async def _handle_unregistered_user(self, user_id: str, phone_number: str, message: str) -> str:
        """Handle messages from unregistered users."""
        # Check if user is in registration flow
        if phone_number in self.registration_handler.registration_state:
            return await self.registration_handler.handle_registration_flow(user_id, phone_number, message)
        
        # Check if user wants to register
        message_lower = message.lower()
        if any(word in message_lower for word in ["start", "register", "signup", "begin", "hello", "hi"]):
            return await self.registration_handler.handle_registration_flow(user_id, phone_number, message)
        
        # Default response for unregistered users
        return (
            "👋 Welcome to BetTask - Your Personal Accountability System!\n\n"
            "It looks like you're new here. To start using BetTask, I need to create your account first.\n\n"
            "Type 'register' or 'start' to begin, or send any message to continue with registration."
        )
    
    async def _generate_user_greeting(self, user_profile: Dict[str, Any]) -> Optional[str]:
        """Generate personalized greeting for registered users."""
        try:
            # Check if user has been greeted recently (avoid spam)
            # For now, we'll generate greeting for each session
            
            balance = user_profile.get("balance", 0)
            email = user_profile.get("email", "")
            name = email.split("@")[0] if email else "there"
            
            greeting = f"👋 Welcome back, {name}!\n💰 Your current balance: ₹{balance:,.2f}"
            
            # Check for active challenges
            active_challenges = await self.supabase_client.get_user_challenges(
                user_profile["id"], status="active", limit=3
            )
            
            if active_challenges:
                greeting += f"\n\n🎯 You have {len(active_challenges)} active challenge(s):"
                for i, ch in enumerate(active_challenges[:5], 1):
                    deadline = datetime.fromisoformat(ch["deadline"].replace("Z", "+00:00"))
                    time_left = deadline - datetime.now()
                    hours_left = max(0, int(time_left.total_seconds() / 3600))
                    
                    greeting += f"\n{i}. {ch['title']} (₹{ch['amount']})"  # Fixed: use greeting instead of response
                    if hours_left > 0:
                        greeting += f" - {hours_left}h left"
                    else:
                        greeting += " - ⚠️ OVERDUE"
                
                greeting += "\n\nDon't forget to submit proof when you complete them! 📸"
            
            return greeting
            
        except Exception as e:
            logger.error(f"Error generating greeting: {e}")
            return None
    
    async def _handle_payment_verification(self, user_id: str, phone_number: str, media_url: str) -> str:
        """Handle payment screenshot verification."""
        try:
            # Download image data
            async with self.supabase_client.client.storage.from_("payment-proofs").download(media_url) as response:
                if response.status_code != 200:
                    return "❌ Could not download payment screenshot. Please try uploading again."
                
                image_data = await response.read()
            
            return await self.fund_handler.handle_payment_screenshot(user_id, phone_number, image_data)
            
        except Exception as e:
            logger.error(f"Error handling payment verification: {e}")
            return "❌ Error processing payment screenshot. Please try again."
    
    async def _route_by_intent(
        self, 
        intent_result, 
        user_id: str, 
        phone_number: str, 
        message: str,
        user_profile: Dict[str, Any]
    ) -> str:
        """Route message to handler based on classified intent."""
        intent = intent_result.intent
        
        try:
            if intent == "get_balance":
                return await self.balance_handler.handle_balance_request(user_id)
            
            elif intent == "cancel_conversation":
                # Clear any conversation state
                if phone_number in self.bet_conversation_state:
                    del self.bet_conversation_state[phone_number]
                return (
                    "✅ Cancelled! What would you like to do instead?\n\n"
                    "• Create a challenge\n" 
                    "• Check balance\n"
                    "• See your challenges\n"
                    "• Add funds"
                )
            
            elif intent == "modify_recent_challenge":
                # Handle recent challenge modifications
                return await self._handle_recent_challenge_modification(
                    user_id, phone_number, message, intent_result.extracted_data, user_profile
                )
            
            elif intent in ["bet_amount", "bet_amount_all"]:
                # User wants to create a challenge but started with the amount
                self.bet_conversation_state[phone_number] = {
                    'stage': 'waiting_for_goal',
                    'amount': intent_result.extracted_data.get('amount', user_profile.get('balance', 100)) if intent == 'bet_amount' else user_profile.get('balance', 100)
                }
                
                amount = self.bet_conversation_state[phone_number]['amount']
                
                return (
                    f"💰 Got it! You want to bet ₹{amount}.\n\n"
                    f"What's your goal? For example:\n"
                    f"• 'Complete 5 workouts this week'\n"
                    f"• 'Read 20 pages daily'\n"
                    f"• 'Finish the project by Friday'"
                )
            
            elif intent == "create_challenge_with_amount":
                # Challenge with amount already specified
                title = intent_result.extracted_data.get('title', message)
                amount = intent_result.extracted_data.get('amount', 0)
                balance = user_profile.get("balance", 0)
                
                if amount > balance:
                    return (
                        f"❌ That's more than your balance!\n\n"
                        f"💰 You want to bet: ₹{amount}\n"
                        f"💳 Your balance: ₹{balance}\n\n"
                        f"Please enter a smaller amount or type 'all' to bet your full balance."
                    )
                
                # Start the confirmation flow
                self.bet_conversation_state[phone_number] = {
                    'stage': 'waiting_for_confirmation',
                    'challenge_text': title,
                    'amount': amount,
                    'task_type': 'one-time'
                }
                
                return (
                    f"📋 Challenge Summary:\n"
                    f"• Goal: {title}\n"
                    f"• Type: One-time\n"
                    f"• Bet: ₹{amount}\n\n"
                    f"Reply 'yes' to create this challenge, or 'edit' to change something."
                )
            
            elif intent == "create_challenge_intent":
                balance = user_profile.get("balance", 0)
                
                if balance == 0:
                    return (
                        "Love the motivation! 🔥\n\n"
                        "But you'll need some funds in your wallet first to make it interesting.\n\n"
                        "Type 'add funds' to get started!"
                    )
                
                # Extract and clean the goal from the extracted data
                raw_goal = intent_result.extracted_data.get("goal", message)
                suggested_amount = intent_result.extracted_data.get("amount")
                
                # Clean up the goal text to extract the actual activity
                goal = self._extract_clean_goal(raw_goal)
                
                # Start the challenge creation conversation
                self.bet_conversation_state[phone_number] = {
                    'stage': 'waiting_for_amount',
                    'goal': goal
                }
                
                if suggested_amount:
                    # User provided both goal and amount
                    self.bet_conversation_state[phone_number]['amount'] = suggested_amount
                    self.bet_conversation_state[phone_number]['stage'] = 'waiting_for_confirmation'
                    
                    return f"Perfect! '{goal}' for ₹{suggested_amount} 💪\n\nSound good? Say 'yes' to make it happen! 🚀"
                else:
                    return f"Nice! '{goal}' 🎯\n\nHow much you want to bet? You've got ₹{balance} to work with 💰"
            
            elif intent == "select_challenge":
                # Handle challenge selection for completion
                selection = intent_result.extracted_data.get('selection', '1')
                return await self._handle_challenge_selection(user_id, phone_number, selection)
                
            elif intent == "list_challenges":
                return await self.challenge_handler.handle_list_challenges(
                    user_id, phone_number, message, intent_result.extracted_data, user_profile
                )
                
            elif intent == "submit_completion":
                return await self._handle_completion_submission(user_id, phone_number, message)
                
            elif intent == "add_funds":
                return await self.fund_handler.handle_add_funds(user_id, phone_number, message)
                
            elif intent == "withdraw_funds":
                return await self.withdrawal_handler.handle_withdraw_funds(user_id, phone_number, message)
                
            elif intent == "help":
                return await self.help_handler.handle_help(
                    user_id, phone_number, message, intent_result.extracted_data, user_profile
                )
                
            elif intent == "transaction_history":
                return await self.balance_handler.handle_transaction_history(user_id)
                
            elif intent == "general_chat":
                # Use AI for natural conversation instead of static responses
                try:
                    # Generate human-like conversational response
                    response = await self.gemini_client.generate_conversational_response(
                        message=message,
                        user_context=user_profile,
                        conversation_history=None  # Could add conversation history tracking here
                    )
                    return response
                except Exception as e:
                    logger.error(f"Error generating conversational response: {e}")
                    # Fallback to helpful but friendly response
                    balance = user_profile.get("balance", 0)
                    
                    # Be more conversational in fallbacks too
                    greetings = ["hi", "hello", "hey"]
                    if any(greeting in message.lower() for greeting in greetings):
                        if balance > 0:
                            return "Hey! 👋 What goal do you want to work on today?"
                        else:
                            return "Hi there! 👋 Ready to start crushing some goals? Type 'add funds' to get started!"
                    
                    thanks_words = ["thanks", "thank you"]
                    if any(thanks in message.lower() for thanks in thanks_words):
                        return "You got it! 💪 Keep pushing yourself!"
                    
                    # Default encouraging response
                    if balance > 0:
                        return "What's on your mind? Tell me something you want to work on! 🎯"
                    else:
                        return "I'm here to help you achieve your goals! Type 'add funds' to get started with challenges 💪"
                
            elif intent == "edit_challenge":
                # Handle challenge editing - redirect to web app for now
                return (
                    "✏️ **Challenge Editing**\n\n"
                    "For the best editing experience, please use our web app:\n\n"
                    "🌐 **https://dare-you-succeed.vercel.app/**\n\n"
                    "✨ **You can easily:**\n"
                    "• Modify challenge goals\n"
                    "• Change bet amounts\n"
                    "• Update deadlines\n"
                    "• Switch between one-time/recurring\n\n"
                    "💡 Much easier than text editing!"
                )
                
            elif intent == "completion_or_verification":
                # Handle completion claims and verification requests - redirect to web app
                return (
                    "🎉 **Ready to submit proof?**\n\n"
                    "📱 **Use our web app for verification:**\n"
                    "🌐 **https://dare-you-succeed.vercel.app/**\n\n"
                    "✨ **Benefits:**\n"
                    "• Select your specific challenge\n"
                    "• Upload high-quality photos\n"
                    "• Get instant AI verification\n"
                    "• Better success rate\n\n"
                    "🚀 **Much easier than WhatsApp!**"
                )
                
            elif intent == "information_request":
                # Handle information/help requests
                if any(word in message.lower() for word in ['submit', 'proof', 'verify', 'verification']):
                    return (
                        "📖 **How to Submit Proof:**\n\n"
                        "🌐 **Use our web app:** https://dare-you-succeed.vercel.app/\n\n"
                        "📝 **Steps:**\n"
                        "1. Open the web app\n"
                        "2. Log in with your account\n"
                        "3. Select your challenge\n"
                        "4. Upload proof photo\n"
                        "5. Get instant AI verification\n\n"
                        "💡 **Much easier than WhatsApp messaging!**"
                    )
                else:
                    # General help
                    return await self.help_handler.handle_help(
                        user_id, phone_number, message, intent_result.extracted_data, user_profile
                    )
                
            else:
                # Unknown intent, provide helpful response
                return (
                    f"🤔 **I'm not sure what you'd like to do.**\n\n"
                    "💡 **Here are some things I can help with:**\n\n"
                    "• 'balance' - Check your wallet balance\n"
                    "• 'create challenge' - Set a new goal\n"
                    "• 'my challenges' - View your challenges\n"
                    "• 'add funds' - Add money to wallet\n"
                    "• 'withdraw' - Withdraw money from wallet\n"
                    "• 'help' - See all available commands\n\n"
                    "📱 **For verification, use:** https://dare-you-succeed.vercel.app/"
                )
                
        except Exception as e:
            logger.error(f"Error in intent routing: {e}")
            return "❌ Sorry, I had trouble processing your request. Please try again."
    
    async def _handle_completion_submission(self, user_id: str, phone_number: str, message: str) -> str:
        """Handle text-based completion claims - redirect to web app for proof submission."""
        try:
            # Get active challenges
            active_challenges = await self.supabase_client.get_user_challenges(user_id, status="active", limit=50)
            
            if not active_challenges:
                return (
                    "🎯 **No Active Challenges**\n\n"
                    "You don't have any active challenges to complete.\n\n"
                    "💡 Create a new challenge by sending:\n"
                    "\"I want to [goal], bet ₹[amount]\"\n\n"
                    "Example: \"I want to go to gym today, bet ₹100\""
                )
            
            # Always redirect to web app for verification
            challenge_count = len(active_challenges)
            return (
                f"🎉 Ready to submit proof?\n\n"
                f"📱 Use our web app:\n"
                f"🌐 dare-you-succeed.vercel.app\n\n"
                f"Active challenges ({challenge_count}):\n"
                + "\n".join([f"• {ch['title']} (₹{ch['amount']})" for ch in active_challenges[:3]])
                + (f"\n+ {challenge_count - 3} more" if challenge_count > 3 else "")
                + "\n\n🚀 Click link to submit proof!"
            )
                
        except Exception as e:
            logger.error(f"Error handling completion submission: {e}")
            return "❌ Sorry, I had trouble processing your completion. Please try again."
    
    async def _create_challenge_direct(self, user_id: str, title: str, amount: int, balance: float) -> str:
        """Create a challenge directly without conversation flow."""
        try:
            # Create challenge directly without AI delay
            deadline = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
            
            challenge_data = {
                "user_id": user_id,
                "title": title,
                "description": title,
                "task_type": "one-time",
                "amount": amount,  # Already int from intent classification
                "deadline": deadline.isoformat(),
                "verification_method": "photo",
                "verification_details": "Submit clear proof of completion",
                "status": "active"
            }
            
            result = self.supabase_client.client.table("challenges").insert(challenge_data).execute()
            
            if result.data:
                # Deduct amount from balance
                new_balance = balance - amount
                await self.supabase_client.update_user_balance(user_id, new_balance)
                
                # Record transaction
                await self.supabase_client.record_transaction(
                    user_id=user_id,
                    amount=-amount,
                    transaction_type="deduction",
                    description=f"Challenge bet: {title}",
                    challenge_id=result.data[0]["id"]
                )
                
                return (
                    f"✅ Challenge Created!\n\n"
                    f"🎯 {title}\n"
                    f"💰 Bet: ₹{amount}\n"
                    f"⏰ Deadline: {deadline.strftime('%b %d, %I:%M %p')}\n\n"
                    f"💡 Submit proof at:\n"
                    f"🌐 dare-you-succeed.vercel.app\n\n"
                    f"New balance: ₹{new_balance}"
                )
            else:
                return "❌ Error creating challenge. Please try again."
                
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            return "❌ Error creating challenge. Please try again."
    
    async def _handle_challenge_selection(self, user_id: str, phone_number: str, selection: str) -> str:
        """Handle user selecting challenge numbers - redirect to web app for verification."""
        try:
            # If user sends a number, they're probably trying to select a challenge for verification
            # Redirect them to the web app instead
            if selection.isdigit():
                logger.info(f"🔢 User {phone_number} sent number {selection} - redirecting to web app")
                return (
                    f"🎯 **Want to verify challenge #{selection}?**\n\n"
                    f"📱 **Please use our web app for verification:**\n"
                    f"🌐 **https://dare-you-succeed.vercel.app/**\n\n"
                    f"✨ **Benefits:**\n"
                    f"• Select your specific challenge easily\n"
                    f"• Upload high-quality photos\n"
                    f"• Get instant verification results\n"
                    f"• Better success rate\n\n"
                    f"🚀 **Much easier than WhatsApp!**"
                )
            
            # For non-numeric input, provide general help
            return (
                "🤔 I'm not sure what you're trying to do.\n\n"
                "💡 **Common actions:**\n"
                "• 'balance' - Check wallet balance\n"
                "• 'my challenges' - View your challenges\n"
                "• 'I will [goal] bet ₹[amount]' - Create challenge\n"
                "• 'add funds' - Add money to wallet\n"
                "• 'help' - See all commands\n\n"
                "📱 **For challenge verification, use:**\n"
                "🌐 **https://dare-you-succeed.vercel.app/**"
            )
                
        except Exception as e:
            logger.error(f"Error handling challenge selection: {e}")
            return (
                "❌ Error processing your request.\n\n"
                "📱 **For challenge verification, please use:**\n"
                "🌐 **https://dare-you-succeed.vercel.app/**"
            )
    
    async def _handle_recent_challenge_modification(self, user_id: str, phone_number: str, message: str, extracted_data: dict, user_profile: Dict[str, Any]) -> str:
        """Handle recent challenge modifications."""
        try:
            # Get recent challenges (last 5 minutes) that might need modification
            from datetime import timedelta
            recent_time = datetime.now() - timedelta(minutes=5)
            
            recent_challenges = await self.supabase_client.get_user_challenges(
                user_id, status="active", limit=5
            )
            
            # Filter to very recent challenges
            very_recent = []
            for challenge in recent_challenges:
                created_at = datetime.fromisoformat(challenge["created_at"].replace("Z", "+00:00"))
                if created_at >= recent_time.replace(tzinfo=created_at.tzinfo):
                    very_recent.append(challenge)
            
            if not very_recent:
                return (
                    "🤔 **No recent challenges to modify.**\n\n"
                    "💡 **To modify a challenge:**\n"
                    "1. First view your challenges: 'my challenges'\n"
                    "2. Then specify which one to modify\n\n"
                    "📱 **Or use our web app for better management:**\n"
                    "🌐 **https://dare-you-succeed.vercel.app/**"
                )
            
            if len(very_recent) == 1:
                # Modify the most recent challenge
                challenge = very_recent[0]
                
                # Handle converting to recurring challenge
                if extracted_data.get('modification_type') == 'make_recurring':
                    frequency = extracted_data.get('frequency', 'daily')
                    special_frequency = extracted_data.get('special_frequency')
                    
                    # Update the challenge to be recurring
                    update_data = {
                        "task_type": "recurring",
                        "recurring_frequency": frequency,
                        "recurring_duration": "1month"
                    }
                    
                    result = self.supabase_client.client.table("challenges").update(update_data).eq("id", challenge["id"]).execute()
                    
                    if result.data:
                        frequency_text = special_frequency if special_frequency else frequency.replace('_', ' ')
                        return (
                            f"✅ **Challenge Updated to Recurring!**\n\n"
                            f"🎯 **Challenge:** {challenge['title']}\n"
                            f"🔄 **Type:** Recurring ({frequency_text})\n"
                            f"💰 **Bet:** ₹{challenge['amount']} {frequency_text.lower()}\n\n"
                            f"📅 **Your challenge will now repeat {frequency_text.lower()}!**\n"
                            f"💡 You'll get reminders and need to submit proof each time.\n\n"
                            f"🚀 **Submit proof at:** https://dare-you-succeed.vercel.app/"
                        )
                    else:
                        return (
                            f"❌ **Error updating challenge to recurring.**\n\n"
                            f"📱 **Please try using our web app:**\n"
                            f"🌐 **https://dare-you-succeed.vercel.app/**"
                        )
                
                # Handle deadline modification
                elif "tomorrow" in message.lower() or "from tomorrow" in message.lower():
                    new_deadline = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)
                    
                    # Update the challenge deadline
                    self.supabase_client.client.table("challenges").update({
                        "deadline": new_deadline.isoformat()
                    }).eq("id", challenge["id"]).execute()
                    
                    return (
                        f"✅ **Challenge Deadline Updated!**\n\n"
                        f"🎯 **Challenge:** {challenge['title']}\n"
                        f"📅 **New Deadline:** {new_deadline.strftime('%B %d, %Y at %I:%M %p')}\n"
                        f"💰 **Bet Amount:** ₹{challenge['amount']}\n\n"
                        f"🔔 You'll get a reminder 2 hours before the new deadline.\n\n"
                        f"💪 Good luck with your challenge!"
                    )
                else:
                    return (
                        f"🎯 **Recent Challenge:** {challenge['title']}\n\n"
                        f"❓ **What would you like to modify?**\n"
                        f"💡 **Examples:**\n"
                        f"• 'Change deadline to tomorrow'\n"
                        f"• 'Extend deadline by 2 days'\n"
                        f"• 'Update deadline to Monday'\n"
                        f"• 'Make this recurring daily'\n\n"
                        f"📱 **Or use our web app for full editing:**\n"
                        f"🌐 **https://dare-you-succeed.vercel.app/**"
                    )
            else:
                # Multiple recent challenges, ask which one
                challenge_list = "\n".join([
                    f"{i+1}. {ch['title']} (₹{ch['amount']})" 
                    for i, ch in enumerate(very_recent)
                ])
                
                return (
                    f"📋 **Recent challenges to modify:**\n\n"
                    f"{challenge_list}\n\n"
                    f"💡 **Please specify which challenge you want to modify:**\n"
                    f"• Reply with the number (1, 2, etc.)\n"
                    f"• Or use more specific language\n\n"
                    f"📱 **For easier editing, use our web app:**\n"
                    f"🌐 **https://dare-you-succeed.vercel.app/**"
                )
                
        except Exception as e:
            logger.error(f"Error handling recent challenge modification: {e}")
            return (
                "❌ **Error modifying challenge.**\n\n"
                "📱 **Please use our web app for modifications:**\n"
                "🌐 **https://dare-you-succeed.vercel.app/**"
            )
    
    def _extract_clean_goal(self, raw_goal: str) -> str:
        """Extract and clean the actual activity from natural language goal text."""
        import re
        
        # Remove common question/request patterns
        patterns_to_remove = [
            r'(?i)^(can you|could you|please|will you|would you)\s*',
            r'(?i)\b(book|create|make|set up|add)\s*(one|a|an)?\s*(task|challenge|goal|bet)?\s*(of|for)?\s*(me)?\s*',
            r'(?i)^(i will|i want to|i would like to|i am going to|i plan to|i\'m going to)\s*',
            r'(?i)\b(bet|rs|inr|rupees|₹)\b',
            r'(?i)\?$',  # Remove trailing question marks
        ]
        
        cleaned_goal = raw_goal.strip()
        
        for pattern in patterns_to_remove:
            cleaned_goal = re.sub(pattern, '', cleaned_goal).strip()
        
        # Handle specific activity extraction
        if 'drinking water' in cleaned_goal.lower() or 'drink water' in cleaned_goal.lower():
            return 'drink water'
        elif 'gym' in cleaned_goal.lower():
            return 'go to gym'
        elif 'study' in cleaned_goal.lower():
            return 'study'
        elif 'read' in cleaned_goal.lower():
            return 'read'
        elif 'exercise' in cleaned_goal.lower() or 'workout' in cleaned_goal.lower():
            return 'exercise'
        
        # If we have a reasonable goal text after cleaning, use it
        if len(cleaned_goal) > 2:
            return cleaned_goal
        else:
            # Fallback to original if cleaning removed too much
            return raw_goal 