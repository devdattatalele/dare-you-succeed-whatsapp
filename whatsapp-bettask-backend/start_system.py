#!/usr/bin/env python3
"""
Start WhatsApp MCP System

This script helps you start both the WhatsApp bridge and Python backend
in the correct order and verifies they're working.
"""

import subprocess
import time
import sys
import asyncio
import aiohttp

async def check_service(url, name):
    """Check if a service is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status == 200
    except:
        return False

async def wait_for_services():
    """Wait for both services to be ready."""
    print("🔍 Waiting for services to start...")
    
    for i in range(30):  # Wait up to 30 seconds
        bridge_ok = await check_service("http://localhost:8080", "Bridge")
        backend_ok = await check_service("http://localhost:8000", "Backend") 
        
        if bridge_ok and backend_ok:
            print("✅ Both services are running!")
            return True
        
        print(f"⏳ Waiting... Bridge: {'✅' if bridge_ok else '❌'} Backend: {'✅' if backend_ok else '❌'}")
        await asyncio.sleep(1)
    
    return False

def main():
    print("🚀 Starting WhatsApp MCP System")
    print("=" * 40)
    
    print("\n📱 Instructions:")
    print("1. I'll start the WhatsApp bridge first")
    print("2. You'll see a QR code - scan it with WhatsApp")
    print("3. Then I'll start the Python backend")
    print("4. Finally, you can test by sending a WhatsApp message")
    
    input("\nPress Enter to start the WhatsApp bridge...")
    
    # Start WhatsApp bridge
    print("\n🔄 Starting WhatsApp bridge...")
    print("👀 Watch for QR code and scan it with your phone!")
    
    try:
        # Start the bridge in a new terminal (macOS)
        bridge_cmd = """
        osascript -e 'tell app "Terminal" to do script "cd \"{}/whatsapp-mcp/whatsapp-bridge\" && go run main.go"'
        """.format('/Users/dev16/Documents/Test project/dare-you-succeed 3')
        
        subprocess.run(bridge_cmd, shell=True)
        
        print("\n⏳ Waiting 10 seconds for bridge to start...")
        time.sleep(10)
        
        # Check if services are ready
        print("\n🔍 Checking service status...")
        services_ready = asyncio.run(wait_for_services())
        
        if services_ready:
            print("\n🎉 SUCCESS! Both services are running!")
            print("\n📱 TEST YOUR SYSTEM:")
            print("   Send these WhatsApp messages to your number:")
            print("   • 'help'")
            print("   • 'balance'") 
            print("   • 'I want to exercise for 30 minutes, bet ₹100'")
            
        else:
            print("\n⚠️ Services may not be fully ready. Check the terminals.")
            
    except Exception as e:
        print(f"\n❌ Error starting services: {e}")
        print("\n🔧 Manual start instructions:")
        print("Terminal 1: cd ../whatsapp-mcp/whatsapp-bridge && go run main.go")
        print("Terminal 2: python main.py")

if __name__ == "__main__":
    main() 