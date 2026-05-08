"""
IAB-style content taxonomy.

A flat list of (category, description) pairs. Description matters —
the embedding classifier embeds the description text, so richer
descriptions yield better similarity matches.

Production note: IAB Content Taxonomy 3.0 has ~700 labels. We use a
hand-picked subset here to keep startup fast and demo behavior
predictable. Expanding the taxonomy is a one-line code change —
just add more entries below.
"""

# (label, description used for embedding)
TAXONOMY: list[tuple[str, str]] = [
    # Ecommerce
    ("Ecommerce > Product Page", "online product listing for purchase, with price, reviews, add to cart"),
    ("Ecommerce > Kitchen Appliances", "toasters, blenders, coffee makers, kitchen gadgets, small home appliances for cooking"),
    ("Ecommerce > Electronics", "laptops, phones, headphones, cameras, consumer electronics product"),
    ("Ecommerce > Apparel", "clothing, shoes, fashion, accessories for sale"),
    ("Ecommerce > Home Goods", "furniture, decor, bedding, household items"),

    # News
    ("News > Technology", "technology news, AI, software, hardware industry news"),
    ("News > Business", "business news, markets, finance, corporate news"),
    ("News > Politics", "politics, government, elections, policy news"),
    ("News > World", "international news, global events, foreign affairs"),
    ("News > Science", "scientific discoveries, research news, space, biology"),

    # Outdoors and lifestyle
    ("Outdoors > Camping", "camping tips, tents, outdoor gear, sleeping bags, campfires"),
    ("Outdoors > Hiking", "hiking trails, backpacking, trekking, outdoor walks, mountain trails"),
    ("Outdoors > Travel", "travel destinations, vacation planning, tourism, trip guides"),
    ("Lifestyle > Food and Cooking", "recipes, cooking, food, restaurants, dining, culinary"),
    ("Lifestyle > Fitness", "exercise, workouts, gym, training, physical fitness"),

    # Tech and software
    ("Technology > Software Development", "programming, coding, software engineering, developer tools"),
    ("Technology > AI and Machine Learning", "artificial intelligence, machine learning, neural networks, large language models"),
    ("Technology > Cloud Computing", "cloud services, AWS, Azure, GCP, infrastructure, devops"),
    ("Technology > Cybersecurity", "security, hacking, malware, data breaches, privacy"),

    # Entertainment
    ("Entertainment > Movies", "films, cinema, movie reviews, Hollywood"),
    ("Entertainment > Music", "music, albums, artists, concerts, songs"),
    ("Entertainment > Gaming", "video games, esports, game reviews, gaming hardware"),
    ("Entertainment > TV and Streaming", "television shows, streaming services, Netflix, series"),

    # Health and finance
    ("Health > Medical", "medical conditions, treatments, doctors, hospitals, health information"),
    ("Health > Wellness", "mental health, wellness, mindfulness, self-care"),
    ("Finance > Personal Finance", "budgeting, saving, retirement, personal money management"),
    ("Finance > Investing", "stocks, bonds, investing, portfolios, markets"),

    # Education and reference
    ("Education > How-To Guide", "instructional guides, tutorials, step-by-step articles"),
    ("Education > Reference", "encyclopedic information, reference material, definitions"),

    # Generic fallback
    ("General > Blog Post", "personal or editorial blog content, opinion piece"),
]


def get_labels() -> list[str]:
    """Return just the labels."""
    return [label for label, _ in TAXONOMY]


def get_descriptions() -> list[str]:
    """Return just the descriptions (for embedding)."""
    return [desc for _, desc in TAXONOMY]