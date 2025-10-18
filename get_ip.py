#!/usr/bin/env python
"""
Get current IP address for Supabase whitelisting
"""
import requests
import json

def get_ip_address():
    """Get current public IP address"""
    try:
        # Try multiple services to get IP
        services = [
            'https://api.ipify.org?format=json',
            'https://httpbin.org/ip',
            'https://api64.ipify.org?format=json'
        ]

        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'ip' in data:
                        ip = data['ip']
                        print(f"✅ IP from {service}: {ip}")
                        return ip
                    elif 'origin' in data:
                        ip = data['origin'].split(',')[0].strip()
                        print(f"✅ IP from {service}: {ip}")
                        return ip
            except:
                continue

        # Fallback to a simple request
        response = requests.get('https://api.ipify.org', timeout=5)
        if response.status_code == 200:
            ip = response.text.strip()
            print(f"✅ IP from ipify: {ip}")
            return ip

    except Exception as e:
        print(f"❌ Error getting IP: {e}")

    print("❌ Could not determine IP address")
    return None

if __name__ == "__main__":
    print("🌐 Getting your current IP address for Supabase whitelisting...")
    print("=" * 60)

    ip = get_ip_address()

    if ip:
        print("
📋 Your IP address to whitelist in Supabase:"        print(f"   🔑 {ip}")
        print("
📝 Steps to add to Supabase:"        print("1. Go to: https://supabase.com/dashboard/project/mpldpvzuuptljxvmdihg/settings/database"        print(f"2. In 'Allowed IP addresses', add: {ip}")
        print("3. Save changes"        print("4. Try running: python manage.py migrate"
    else:
        print("
🔧 Alternative ways to find your IP:"        print("- Visit: https://whatismyipaddress.com/")
        print("- Search: 'what is my ip' in Google")
        print("- Check your router settings")
