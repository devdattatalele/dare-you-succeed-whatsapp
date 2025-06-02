"""
Intent Router

Routes WhatsApp messages to appropriate handlers based on intent classification.
Handles user registration, fund management, and all user interactions.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
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
                return (
                    f"🎯 **What would you like to bet on?**\n\n"
                    f"💡 **Tell me your goal, like:**\n"
                    f"• 'Go to gym today'\n"
                    f"• 'Complete my project by Friday'\n"
                    f"• 'Read 20 pages'\n"
                    f"• 'Exercise 3 times this week'\n\n"
                    f"💰 Your balance: ₹{balance}\n"
                    f"📅 Say 'recurring' for daily/weekly challenges"
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
            return (
                "🤔 I'm not sure what you'd like to do.\n\n"
                "💡 Try these:\n"
                "• 'balance' - Check wallet\n"
                "• 'my challenges' - View challenges\n"
                "• 'add funds' - Add money\n"
                "• 'help' - See commands\n\n"
                "📱 Verification: dare-you-succeed.vercel.app"
            )
                
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            return "Sorry, I encountered an error. Please try again or contact support."
    
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
        if state.get('stage') == 'waiting_for_goal' or ('challenge_text' not in state and 'amount' not in state):
            # If user is trying to provide an amount before the goal, extract both
            amount_match = re.search(r'(\d+)', message)
            if amount_match:
                amount = int(amount_match.group(1))
                # Save amount but still ask for a proper goal
                state['amount'] = amount
                
                # Remove amount part to extract goal text
                goal_text = re.sub(r'\b\d+\b', '', message).strip()
                # Remove common betting phrases to extract actual goal
                goal_text = re.sub(r'(?i)\b(bet|rs|inr|rupees|₹)\b', '', goal_text).strip()
                
                if len(goal_text) > 5:  # If there's a reasonable goal text
                    state['challenge_text'] = goal_text
                    state['stage'] = 'waiting_for_confirmation'
                    
                    return (
                        f"🎯 I understand you want to:\n"
                        f"• Goal: {goal_text}\n"
                        f"• Bet: ₹{amount}\n\n"
                        f"Is this correct? Reply 'yes' to create this challenge or provide a better goal description."
                    )
                else:
                    # We have amount but need goal
                    state['stage'] = 'waiting_for_goal'
                    return (
                        f"💰 Got it! You want to bet ₹{amount}.\n\n"
                        f"🎯 What's your goal? For example:\n"
                        f"• 'Complete 5 workouts this week'\n"
                        f"• 'Read 20 pages daily'\n"
                        f"• 'Finish the project by Friday'"
                    )
            
            # User provided a goal without amount
            state['challenge_text'] = message
            state['stage'] = 'waiting_for_amount'
            
            balance = user_profile.get("balance", 0)
            return (
                f"🎯 Got it! Your goal is: '{message}'\n\n"
                f"💰 How much do you want to bet on this goal?\n"
                f"💳 Your balance: ₹{balance}\n\n"
                f"Reply with an amount (e.g., '100') or 'recurring' for a daily/weekly challenge."
            )
        
        # If user says "recurring" at any point, handle frequency (but not if already waiting for frequency)
        if (message.lower().strip() in ['recurring', 'repeat'] or 
            (message.lower().strip() in ['daily', 'weekly'] and state.get('stage') != 'waiting_for_frequency')):
            state['task_type'] = 'recurring'
            state['stage'] = 'waiting_for_frequency'
            
            # If we already have a goal, show it
            goal_text = state.get('challenge_text', 'your goal')
            
            return (
                f"📅 Making this a recurring challenge!\n\n"
                f"🎯 Goal: {goal_text}\n\n"
                f"How often? Reply with:\n"
                f"• 'daily' - Every day\n"
                f"• 'weekly' - Once a week\n"
                f"• '3 times per week'"
            )
        
        # Handle frequency selection
        if state.get('stage') == 'waiting_for_frequency':
            frequency_map = {
                'daily': 'daily',
                'weekly': 'weekly', 
                'twice a week': 'twice_weekly',
                '2 times per week': 'twice_weekly',
                '3 times per week': 'thrice_weekly',
                'thrice a week': 'thrice_weekly'
            }
            
            freq_input = message.lower().strip()
            frequency = frequency_map.get(freq_input, 'daily')  # Default to daily
            
            state['recurring_frequency'] = frequency
            
            # If we already have amount, go to confirmation
            if 'amount' in state:
                state['stage'] = 'waiting_for_confirmation'
                goal_text = state.get('challenge_text', 'your goal')
                amount = state['amount']
                
                return (
                    f"📋 Challenge Summary:\n"
                    f"• Goal: {goal_text}\n"
                    f"• Type: {frequency.replace('_', ' ')}\n"
                    f"• Bet: ₹{amount}\n\n"
                    f"Reply 'yes' to create this challenge, or 'edit' to change something."
                )
            else:
                # Need amount
                state['stage'] = 'waiting_for_amount'
                balance = user_profile.get("balance", 0)
                
                return (
                    f"📅 Set to {frequency.replace('_', ' ')}!\n\n"
                    f"💰 How much do you want to bet?\n"
                    f"💳 Your balance: ₹{balance}\n\n"
                    f"Reply with an amount (e.g., '100', '₹50', 'all')"
                )
        
        # Handle amount stage
        if state.get('stage') == 'waiting_for_amount':
            balance = user_profile.get("balance", 0)
            
            # Handle "bet all" or similar natural language
            if intent_result.intent == 'bet_amount_all':
                if balance <= 0:
                    return (
                        f"❌ You don't have any balance to bet!\n\n"
                        f"💳 Current balance: ₹{balance}\n\n"
                        f"Please add funds first by typing 'add funds'."
                    )
                amount = int(balance)  # Bet all available balance
                
            elif intent_result.intent == 'bet_amount':
                amount = intent_result.extracted_data.get('amount', 0)
                
            else:
                # Try to extract amount from message
                amount_match = re.search(r'(\d+)', message)
                if amount_match:
                    amount = int(amount_match.group(1))
                else:
                    # Check if message might contain a goal instead of amount
                    if len(message) > 5 and not any(word in message.lower() for word in ['yes', 'no', 'ok', 'sure', 'edit']):
                        # User might be trying to change/set the goal
                        state['challenge_text'] = message
                        return (
                            f"🎯 Updated your goal to: '{message}'\n\n"
                            f"💰 Now, how much do you want to bet on this goal?\n"
                            f"💳 Your balance: ₹{balance}\n\n"
                            f"Reply with a number like '100' or '₹200' or 'all'."
                        )
                    else:
                        return (
                            f"❌ I couldn't understand the amount.\n\n"
                            f"🎯 Goal: {state.get('challenge_text', 'your challenge')}\n"
                            f"💰 Your balance: ₹{balance}\n\n"
                            f"Please just reply with a number like '100' or '200'."
                        )
            
            if amount > balance:
                return (
                    f"❌ That's more than your balance!\n\n"
                    f"💰 You want to bet: ₹{amount}\n"
                    f"💳 Your balance: ₹{balance}\n\n"
                    f"Please enter a smaller amount or type 'all' to bet your full balance."
                )
            
            if amount <= 0:
                return (
                    f"❌ You need to bet at least ₹1.\n\n"
                    f"How much would you like to bet on this challenge?"
                )
            
            # Save amount and move to confirmation
            state['amount'] = amount
            state['stage'] = 'waiting_for_confirmation'
            
            goal_text = state.get('challenge_text', 'your goal')
            task_type = state.get('task_type', 'one-time')
            frequency = state.get('recurring_frequency', 'daily' if task_type == 'recurring' else None)
            
            if task_type == 'recurring':
                return (
                    f"📋 Challenge Summary:\n"
                    f"• Goal: {goal_text}\n"
                    f"• Type: {frequency.replace('_', ' ')}\n"
                    f"• Bet: ₹{amount}\n\n"
                    f"Reply 'yes' to create this challenge, or 'edit' to change something."
                )
            else:
                return (
                    f"📋 Challenge Summary:\n"
                    f"• Goal: {goal_text}\n"
                    f"• Type: One-time\n"
                    f"• Bet: ₹{amount}\n\n"
                    f"Reply 'yes' to create this challenge, or 'edit' to change something."
                )
        
        # Handle confirmation stage
        if state.get('stage') == 'waiting_for_confirmation':
            if message.lower() in ['yes', 'y', 'yeah', 'yep', 'confirm', 'ok', 'okay', 'sure', 'create']:
                # Create the challenge
                try:
                    balance = user_profile.get("balance", 0)
                    challenge_title = state.get('challenge_text', 'My challenge')
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
                            type_text = frequency.replace('_', ' ').capitalize()
                        
                        return (
                            f"✅ Challenge Created!\n\n"
                            f"🎯 {challenge_title}\n"
                            f"📋 Type: {type_text}\n"
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
            
            elif message.lower() in ['edit', 'change', 'modify', 'no']:
                # Ask what they want to edit
                return (
                    f"What would you like to change?\n\n"
                    f"• 'goal' - Change the challenge description\n"
                    f"• 'amount' - Change the bet amount\n"
                    f"• 'type' - Change between one-time/recurring\n\n"
                    f"Or type 'cancel' to start over."
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
                        f"• Goal: {state.get('challenge_text', 'your goal')}\n"
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
                        f"• '3 times per week'"
                    )
            
            # Handle amounts or goals sent directly during confirmation
            amount_match = re.search(r'(\d+)', message)
            if amount_match:
                amount = int(amount_match.group(1))
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
                
                goal_text = state.get('challenge_text', 'your goal')
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
                state['challenge_text'] = message
                
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
            state['challenge_text'] = message
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
            'create bet', 'new bet', 'start bet'
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
        amount_match = re.search(r'(\d+)', message)
        bet_intent = any(keyword in message_lower for keyword in ['bet', 'betting', 'wager', 'stake', 'challenge', 'let\'s bet', 'i bet', 'i want to bet'])
        
        if amount_match and bet_intent and not any(edit_word in message_lower for edit_word in ['edit', 'modify', 'change', 'update', 'alter']):
            amount = int(amount_match.group(0))
            extracted_data['amount'] = amount
            
            # Extract goal from message by removing amount and betting words
            goal_text = re.sub(r'\b\d+\b', '', message).strip()
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
            amount = int(amount_match.group(0))
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
            'new challenge', 'make challenge', 'start challenge', 'i want you to create'
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
            
            elif intent == "modify_challenge":
                # Handle challenge modifications like deadline changes
                return await self._handle_challenge_modification(user_id, phone_number, message, intent_result.extracted_data)
            
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
                # User wants to create a challenge with just the goal
                challenge_text = intent_result.extracted_data.get('challenge_text', message)
                
                # Check if it contains a bet intent but wasn't classified correctly
                bet_keywords = ['bet', 'betting', 'wager', 'stake', 'gamble']
                has_bet_keyword = any(keyword in challenge_text.lower() for keyword in bet_keywords)
                
                # Try to extract amount if there's a betting keyword
                amount = None
                if has_bet_keyword:
                    amount_match = re.search(r'(\d+)', challenge_text)
                    if amount_match:
                        amount = int(amount_match.group(1))
                        # Extract the goal without the amount and betting words
                        goal_text = re.sub(r'\b\d+\b', '', challenge_text).strip()
                        for keyword in bet_keywords:
                            goal_text = re.sub(r'(?i)\b' + keyword + r'\b', '', goal_text).strip()
                        
                        # Only use if we have a reasonable goal text
                        if len(goal_text) > 5:
                            # We extracted both goal and amount
                            self.bet_conversation_state[phone_number] = {
                                'stage': 'waiting_for_confirmation',
                                'challenge_text': goal_text,
                                'amount': amount,
                                'task_type': 'one-time'
                            }
                            
                            return (
                                f"📋 Challenge Summary:\n"
                                f"• Goal: {goal_text}\n"
                                f"• Type: One-time\n"
                                f"• Bet: ₹{amount}\n\n"
                                f"Reply 'yes' to create this challenge, or 'edit' to change something."
                            )
                
                # Regular flow - just goal, need amount
                balance = user_profile.get("balance", 0)
                
                # Set conversation state to wait for amount
                self.bet_conversation_state[phone_number] = {
                    'stage': 'waiting_for_amount',
                    'challenge_text': challenge_text,
                    'task_type': 'one-time'  # Default to one-time, user can specify recurring later
                }
                
                return (
                    f"🎯 Great goal! Your challenge: '{challenge_text}'\n\n"
                    f"💰 How much would you like to bet?\n"
                    f"💳 Your balance: ₹{balance}\n\n"
                    f"Reply with an amount (e.g., '100') or 'recurring' for a daily/weekly challenge."
                )
            
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
                # For general chat, provide helpful suggestions based on context
                balance = user_profile.get("balance", 0)
                suggestions = []
                
                if balance > 0:
                    suggestions.append("• Create a challenge: \"I will [goal], bet ₹[amount]\"")
                else:
                    suggestions.append("• Add funds: \"add funds\"")
                
                suggestions.extend([
                    "• Check balance: \"balance\"",
                    "• See challenges: \"my challenges\"",
                    "• Get help: \"help\""
                ])
                
                return (
                    "🤔 I'm not sure what you'd like to do.\n\n"
                    "💡 Try these:\n"
                    "• 'balance' - Check wallet\n"
                    "• 'my challenges' - View challenges\n"
                    "• 'add funds' - Add money\n"
                    "• 'help' - See commands\n\n"
                    "📱 Verification: dare-you-succeed.vercel.app"
                )
                
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
    
    async def _handle_challenge_modification(self, user_id: str, phone_number: str, message: str, extracted_data: dict) -> str:
        """Handle challenge modifications like deadline changes."""
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
                
                # Handle deadline modification
                if "tomorrow" in message.lower() or "from tomorrow" in message.lower():
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
                        f"• 'Update deadline to Monday'\n\n"
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
            logger.error(f"Error handling challenge modification: {e}")
            return (
                "❌ **Error modifying challenge.**\n\n"
                "📱 **Please use our web app for modifications:**\n"
                "🌐 **https://dare-you-succeed.vercel.app/**"
            ) 