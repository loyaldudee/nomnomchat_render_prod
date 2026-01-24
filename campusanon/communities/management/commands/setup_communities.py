from django.core.management.base import BaseCommand
from communities.models import Community
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Generates the standard set of college communities'

    def handle(self, *args, **kwargs):
        self.stdout.write("🏗️  Building Communities...")

        # DEFINING THE RULES
        # Format: (Branch Name, has_divisions_boolean)
        
        # Years 1 & 2: All branches + ARE
        branches_y1_y2 = [
            ("COMP", True),  # Has A & B
            ("IT", True),    # Has A & B
            ("ENTC", True),  # Has A & B
            ("MECH", False), # Single division
            ("ARE", False),  # Single division
        ]

        # Year 3: No ARE
        branches_y3 = [
            ("COMP", True),
            ("IT", True),
            ("ENTC", True),
            ("MECH", False),
        ]

        # Year 4: No ARE, and IT becomes single division
        branches_y4 = [
            ("COMP", True),
            ("IT", False),   # NO A/B for 4th Year IT
            ("ENTC", True),
            ("MECH", False),
        ]

        # MAP YEARS TO CONFIGS
        year_configs = {
            1: branches_y1_y2,
            2: branches_y1_y2,
            3: branches_y3,
            4: branches_y4
        }

        # GENERATION LOGIC
        count = 0
        for year, config in year_configs.items():
            for branch, has_divisions in config:
                divisions = ["A", "B"] if has_divisions else [None]

                for div in divisions:
                    # Create Name: "1st Year COMP A" or "4th Year MECH"
                    div_str = f" {div}" if div else ""
                    name = f"{year} {branch}{div_str}"
                    
                    # Create Slug: "1-comp-a" or "4-mech"
                    slug_str = f"{year}-{branch}{'-'+div if div else ''}"
                    slug = slugify(slug_str)

                    # Create or Get (Safe to run multiple times)
                    obj, created = Community.objects.get_or_create(
                        year=year,
                        branch=branch,
                        division=div,
                        defaults={
                            'name': name,
                            'slug': slug,
                            'is_global': False
                        }
                    )
                    
                    if created:
                        self.stdout.write(f"   ✅ Created: {name}")
                        count += 1
                    else:
                        self.stdout.write(f"   Note: {name} already exists")

        self.stdout.write(f"🎉 Done! Created {count} new communities.")