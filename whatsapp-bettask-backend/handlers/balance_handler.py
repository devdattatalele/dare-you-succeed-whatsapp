"""
Balance Handler

Handles balance and transaction operations:
- Balance inquiries
- Transaction history
- Wallet management
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from services.supabase_client import SupabaseClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BalanceHandler:
    """Handles balance and transaction operations."""
    
    def __init__(self, supabase_client: SupabaseClient):
        """
        Initialize balance handler.
        
        Args:
            supabase_client: Supabase client instance
        """
        self.supabase = supabase_client
        logger.info("Balance handler initialized")
    
    async def handle_get_balance(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle balance inquiry request.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            message_content: Original message content
            extracted_data: Data extracted by AI
            user_context: User context information
            
        Returns:
            str: Response message with balance information
        """
        try:
            logger.info(f"Getting balance for user {user_id}")
            
            # Get current balance
            balance = await self.supabase.get_user_balance(user_id)
            
            # Get challenge statistics
            active_challenges = await self.supabase.get_user_challenges(
                user_id, status="active"
            )
            pending_challenges = await self.supabase.get_user_challenges(
                user_id, status="pending_verification"
            )
            
            # Calculate locked amount (money in active challenges)
            locked_amount = sum(c["amount"] for c in active_challenges)
            
            # Get recent transactions for context
            recent_transactions = await self.supabase.get_user_transactions(
                user_id, limit=3
            )
            
            response = f"""💰 **Your Wallet**

💳 Available Balance: ₹{balance:.2f}
🔒 Locked in Bets: ₹{locked_amount:.2f}
📊 Total: ₹{balance + locked_amount:.2f}

📈 **Quick Stats:**
• Active Challenges: {len(active_challenges)}
• Pending Verification: {len(pending_challenges)}
• Success Rate: {user_context.get('success_rate', 0)}%"""

            if recent_transactions:
                response += "\n\n💸 **Recent Activity:**"
                for transaction in recent_transactions:
                    amount = transaction["amount"]
                    trans_type = transaction["transaction_type"]
                    description = transaction["description"]
                    
                    emoji = "+" if amount > 0 else "-"
                    response += f"\n{emoji}₹{abs(amount):.2f} - {description}"
            
            response += "\n\n💡 Type 'history' for full transaction history"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return "❌ Sorry, I couldn't fetch your balance. Please try again."
    
    async def handle_transaction_history(
        self,
        user_id: str,
        phone_number: str,
        message_content: str,
        extracted_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Handle transaction history request.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            message_content: Original message content
            extracted_data: Data extracted by AI
            user_context: User context information
            
        Returns:
            str: Response message with transaction history
        """
        try:
            logger.info(f"Getting transaction history for user {user_id}")
            
            # Get transaction history
            transactions = await self.supabase.get_user_transactions(
                user_id, limit=15
            )
            
            if not transactions:
                return """📊 **Transaction History**

No transactions yet!

🎯 Start by creating your first challenge:
"I want to [goal], bet ₹[amount]"

💰 You start with ₹1000 balance."""
            
            response = "📊 **Transaction History**\n\n"
            
            # Group transactions by type
            deposits = [t for t in transactions if t["transaction_type"] == "deposit"]
            deductions = [t for t in transactions if t["transaction_type"] == "deduction"]
            refunds = [t for t in transactions if t["transaction_type"] == "refund"]
            
            # Show recent transactions
            response += "🕐 **Recent Transactions:**\n"
            for transaction in transactions[:10]:
                amount = transaction["amount"]
                trans_type = transaction["transaction_type"]
                description = transaction["description"]
                created_at = transaction["created_at"]
                
                # Format date
                try:
                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = date_obj.strftime("%b %d, %I:%M %p")
                except:
                    date_str = created_at[:10]
                
                # Format amount with emoji
                if amount > 0:
                    amount_str = f"+₹{amount:.2f}"
                    emoji = "💚"
                else:
                    amount_str = f"-₹{abs(amount):.2f}"
                    emoji = "💸"
                
                response += f"{emoji} {amount_str} - {description}\n    {date_str}\n\n"
            
            # Summary statistics
            total_bet = sum(abs(t["amount"]) for t in deductions)
            total_won = sum(t["amount"] for t in refunds)
            total_lost = total_bet - total_won
            
            response += f"""📈 **Summary:**
Total Bet: ₹{total_bet:.2f}
Won Back: ₹{total_won:.2f}
Net Loss: ₹{total_lost:.2f}

💡 Keep challenging yourself to improve!"""
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return "❌ Sorry, I couldn't fetch your transaction history. Please try again."
    
    def _format_transaction_type(self, trans_type: str) -> str:
        """Format transaction type for display."""
        type_mapping = {
            "deposit": "💳 Deposit",
            "deduction": "💸 Bet Placed", 
            "refund": "💚 Challenge Won"
        }
        return type_mapping.get(trans_type, trans_type.title())

    async def handle_balance_request(self, user_id: str) -> str:
        """
        Handle simple balance request (method expected by intent router).
        
        Args:
            user_id: User ID
            
        Returns:
            str: Response message with balance information
        """
        try:
            logger.info(f"Getting balance for user {user_id}")
            
            # Get current balance
            balance = await self.supabase.get_user_balance(user_id)
            
            # Get challenge statistics
            active_challenges = await self.supabase.get_user_challenges(
                user_id, status="active"
            )
            
            # Calculate locked amount (money in active challenges)
            locked_amount = sum(c["amount"] for c in active_challenges)
            
            response = f"""💰 **Your Wallet Status**

💳 Available Balance: ₹{balance:.2f}
🔒 Locked in Bets: ₹{locked_amount:.2f}
📊 Total Wallet: ₹{balance + locked_amount:.2f}

📈 **Summary:**
• Active Challenges: {len(active_challenges)}

💡 Type 'history' for transaction details
🎯 Type 'add funds' to add money
🚀 Type 'create challenge' to start betting!"""
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return "❌ Sorry, I couldn't fetch your balance. Please try again." 