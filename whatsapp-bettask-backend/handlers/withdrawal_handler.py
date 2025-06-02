"""
Withdrawal Handler

Manages money withdrawal from user wallets including:
- Withdrawal request processing
- Active challenge verification
- Payment proof storage
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from services.supabase_client import SupabaseClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WithdrawalHandler:
    """Handler for money withdrawal from wallets."""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        # Store withdrawal state for users in progress
        self.withdrawal_state = {}
    
    async def handle_withdraw_funds(
        self, 
        user_id: str, 
        phone_number: str, 
        message: str
    ) -> str:
        """
        Handle withdrawal request.
        
        Args:
            user_id: User ID
            phone_number: User's WhatsApp number
            message: User's input message
            
        Returns:
            str: Response message
        """
        try:
            # Check if user is already in withdrawal flow
            if phone_number in self.withdrawal_state:
                return await self._continue_withdrawal(phone_number, message)
            else:
                return await self._start_withdrawal(phone_number, user_id)
                
        except Exception as e:
            logger.error(f"Error in withdrawal flow: {e}")
            return "❌ Sorry, there was an error processing your withdrawal request. Please try again."
    
    async def _start_withdrawal(self, phone_number: str, user_id: str) -> str:
        """Start the withdrawal process."""
        try:
            # Check if user has active challenges
            active_challenges = await self.supabase_client.get_user_challenges(
                user_id, status="active"
            )
            
            if active_challenges:
                challenge_list = "\n".join([
                    f"• {ch['title']} (₹{ch['bet_amount']})" 
                    for ch in active_challenges
                ])
                
                return (
                    "⚠️ **Cannot Withdraw - Active Challenges**\n\n"
                    f"You have {len(active_challenges)} active challenge(s):\n\n"
                    f"{challenge_list}\n\n"
                    "Please complete or cancel your challenges before withdrawing money.\n"
                    "This ensures fair play and prevents cheating! 🎯"
                )
            
            # Check current balance
            current_balance = await self.supabase_client.get_user_balance(user_id)
            
            if current_balance <= 0:
                return (
                    "💰 **No Balance to Withdraw**\n\n"
                    f"Your current balance: ₹{current_balance:.2f}\n\n"
                    "Add funds to your wallet first before withdrawing.\n"
                    "Type 'add funds' to add money to your wallet."
                )
            
            # Start withdrawal flow
            self.withdrawal_state[phone_number] = {
                "step": "amount",
                "user_id": user_id,
                "phone": phone_number,
                "max_amount": current_balance,
                "started_at": datetime.now()
            }
            
            return (
                f"💸 **Withdraw Funds**\n\n"
                f"Available Balance: ₹{current_balance:,.2f}\n\n"
                "How much would you like to withdraw?\n"
                f"Enter amount in ₹ (minimum ₹50, maximum ₹{current_balance:,.2f}):\n\n"
                "Example: 100, 500, 1000"
            )
            
        except Exception as e:
            logger.error(f"Error starting withdrawal: {e}")
            return "❌ Error checking withdrawal eligibility. Please try again."
    
    async def _continue_withdrawal(self, phone_number: str, message: str) -> str:
        """Continue with the withdrawal process."""
        state = self.withdrawal_state[phone_number]
        step = state["step"]
        
        if step == "amount":
            return await self._handle_amount_step(phone_number, message)
        elif step == "payment_details":
            return await self._handle_payment_details_step(phone_number, message)
        elif step == "confirm":
            return await self._handle_confirmation_step(phone_number, message)
        else:
            # Invalid state, restart
            del self.withdrawal_state[phone_number]
            return await self._start_withdrawal(phone_number, state["user_id"])
    
    async def _handle_amount_step(self, phone_number: str, amount_str: str) -> str:
        """Handle amount input step."""
        try:
            state = self.withdrawal_state[phone_number]
            max_amount = state["max_amount"]
            
            # Parse amount
            amount = float(amount_str.replace("₹", "").replace(",", "").strip())
            
            if amount < 50:
                return "❌ Minimum withdrawal amount is ₹50. Please enter a higher amount:"
            
            if amount > max_amount:
                return f"❌ Maximum withdrawal amount is ₹{max_amount:,.2f}. Please enter a lower amount:"
            
            # Save amount and move to payment details step
            self.withdrawal_state[phone_number]["amount"] = amount
            self.withdrawal_state[phone_number]["step"] = "payment_details"
            
            return (
                f"💸 **Withdrawal Request: ₹{amount:,.2f}**\n\n"
                "Please provide your payment details:\n\n"
                "📱 **UPI ID** (preferred):\n"
                "Example: yourname@paytm or yourname@googlepay\n\n"
                "🏦 **Or Bank Account Details:**\n"
                "Account Number: XXXX\n"
                "IFSC Code: XXXX\n"
                "Account Holder Name: XXXX\n\n"
                "Enter your preferred payment method:"
            )
            
        except ValueError:
            return "❌ Please enter a valid amount (numbers only):"
    
    async def _handle_payment_details_step(self, phone_number: str, payment_details: str) -> str:
        """Handle payment details input step."""
        state = self.withdrawal_state[phone_number]
        amount = state["amount"]
        
        # Save payment details and move to confirmation
        self.withdrawal_state[phone_number]["payment_details"] = payment_details
        self.withdrawal_state[phone_number]["step"] = "confirm"
        
        return (
            f"📋 **Withdrawal Summary**\n\n"
            f"💰 Amount: ₹{amount:,.2f}\n"
            f"📱 Payment Details: {payment_details}\n\n"
            "⚠️ **Important:**\n"
            "• Processing time: 24-48 hours\n"
            f"• You'll receive: ₹{amount:,.2f} (full amount, no fees)\n\n"
            "Type 'confirm' to proceed with withdrawal, or 'cancel' to abort:"
        )
    
    async def _handle_confirmation_step(self, phone_number: str, message: str) -> str:
        """Handle confirmation step."""
        message_lower = message.lower().strip()
        
        if message_lower == "confirm":
            state = self.withdrawal_state[phone_number]
            amount = state["amount"]
            user_id = state["user_id"]
            payment_details = state["payment_details"]
            
            # Create withdrawal request
            withdrawal_request = await self._create_withdrawal_request(
                user_id, amount, payment_details
            )
            
            # Deduct amount from user balance (no fee)
            total_deduction = amount  # No fee applied
            current_balance = await self.supabase_client.get_user_balance(user_id)
            new_balance = current_balance - total_deduction
            await self.supabase_client.update_user_balance(user_id, new_balance)
            
            # Record transaction
            await self.supabase_client.record_transaction(
                user_id=user_id,
                amount=-amount,
                transaction_type="deduction",
                description=f"Withdrawal request - ID: {withdrawal_request['id'][:8]}"
            )
            
            # Clean up state
            del self.withdrawal_state[phone_number]
            
            return (
                f"✅ **Withdrawal Request Submitted**\n\n"
                f"🆔 Request ID: {withdrawal_request['id'][:8]}\n"
                f"💰 Amount: ₹{amount:,.2f}\n"
                f"💳 New Balance: ₹{new_balance:,.2f}\n\n"
                "⏰ **Processing Time:** 24-48 hours\n"
                f"💰 **You'll receive the full amount:** ₹{amount:,.2f}\n"
                "📧 You'll receive a confirmation once processed.\n\n"
                "Thank you for using BetTask! 🎉"
            )
            
        elif message_lower == "cancel":
            del self.withdrawal_state[phone_number]
            return "❌ Withdrawal cancelled. You can start again by typing 'withdraw'."
        else:
            return "Please type 'confirm' to proceed or 'cancel' to abort the withdrawal:"
    
    async def _create_withdrawal_request(
        self, 
        user_id: str, 
        amount: float, 
        payment_details: str
    ) -> Dict[str, Any]:
        """Create withdrawal request in database."""
        try:
            withdrawal_data = {
                "user_id": user_id,
                "amount": amount,
                "payment_details": payment_details,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "processing_fee": 0.0,  # No fees
                "net_amount": amount  # Full amount
            }
            
            result = self.supabase_client.client.table("withdrawal_requests").insert(withdrawal_data).execute()
            
            if result.data:
                logger.info(f"Created withdrawal request for user {user_id}, amount ₹{amount}")
                return result.data[0]
            else:
                raise Exception("Failed to create withdrawal request")
                
        except Exception as e:
            logger.error(f"Error creating withdrawal request: {e}")
            raise 