#!/bin/bash

echo "🚀 Starting WhatsApp MCP System"
echo "==============================="

echo ""
echo "📱 Instructions:"
echo "1. This will open TWO terminal windows"
echo "2. One for WhatsApp Bridge, one for Python Backend"
echo "3. Both must stay running"
echo "4. Test by sending WhatsApp messages to your number"

echo ""
read -p "Press Enter to start both services..."

# Start WhatsApp Bridge in new terminal
echo "🔄 Starting WhatsApp Bridge..."
osascript -e 'tell app "Terminal" to do script "cd \"'$PWD'/../whatsapp-mcp/whatsapp-bridge\" && echo \"🌉 WhatsApp Bridge Starting...\" && go run main.go"'

# Wait a moment
sleep 3

# Start Python Backend in new terminal  
echo "🔄 Starting Python Backend..."
osascript -e 'tell app "Terminal" to do script "cd \"'$PWD'\" && echo \"🐍 Python Backend Starting...\" && python main.py"'

echo ""
echo "✅ Both services should now be starting!"
echo ""
echo "📱 TEST YOUR SYSTEM:"
echo "   Send these WhatsApp messages to your number:"
echo "   • 'help'"
echo "   • 'balance'"
echo "   • 'I want to exercise for 30 minutes, bet ₹100'"
echo ""
echo "🎯 If you get automatic replies, SUCCESS! 🎉" 