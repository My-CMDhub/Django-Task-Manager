#!/usr/bin/env python
"""
Script to create or update the Site configuration for Django's sites framework.
This is important for correct email verification links.
"""
import os
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.conf import settings
from django.contrib.sites.models import Site

def setup_site():
    """Create or update the default Site object with proper domain"""
    # Get production domain from settings
    domain = getattr(settings, 'SITE_DOMAIN', 'taskmanager-mztm.onrender.com')
    site_name = "Task Manager"
    
    print(f"Setting up Site with domain: {domain}")
    
    # Get the default site
    try:
        site = Site.objects.get(id=settings.SITE_ID)
        print(f"Found existing Site: {site.domain}")
        
        # Update domain if different
        if site.domain != domain:
            site.domain = domain
            site.name = site_name
            site.save()
            print(f"Updated Site domain to: {domain}")
        else:
            print("Site domain already correct")
            
    except Site.DoesNotExist:
        # Create new site if it doesn't exist
        site = Site.objects.create(id=settings.SITE_ID, domain=domain, name=site_name)
        print(f"Created new Site with domain: {domain}")
    
    return site

if __name__ == "__main__":
    site = setup_site()
    print(f"Site configuration complete: ID={site.id}, Domain={site.domain}, Name={site.name}") 