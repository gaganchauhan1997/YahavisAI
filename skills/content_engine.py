"""
YAHAVIS — skills/content_engine.py
Title → complete content package generator.
Outputs: blog post + social captions + SEO meta + email subjects + hashtags.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("yahavis.content_engine")


@dataclass
class ContentPackage:
    title: str
    blog_post: str = ""
    twitter: str = ""
    linkedin: str = ""
    instagram: str = ""
    meta_title: str = ""
    meta_description: str = ""
    keywords: list = field(default_factory=list)
    hashtags: list = field(default_factory=list)
    email_subjects: list = field(default_factory=list)
    tone: str = "professional"

    def to_markdown(self) -> str:
        sections = [
            f"# {self.title}",
            "",
            "## Blog Post",
            self.blog_post,
            "",
            "## Social Captions",
            f"**Twitter/X:** {self.twitter}",
            f"**LinkedIn:** {self.linkedin}",
            f"**Instagram:** {self.instagram}",
            "",
            "## SEO",
            f"**Meta Title:** {self.meta_title}",
            f"**Meta Desc:** {self.meta_description}",
            f"**Keywords:** {', '.join(self.keywords)}",
            f"**Hashtags:** {' '.join(self.hashtags)}",
            "",
            "## Email Subject Lines",
        ] + [f"- {s}" for s in self.email_subjects]
        return "\n".join(sections)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "blog_post": self.blog_post,
            "social": {
                "twitter": self.twitter,
                "linkedin": self.linkedin,
                "instagram": self.instagram,
            },
            "seo": {
                "meta_title": self.meta_title,
                "meta_description": self.meta_description,
                "keywords": self.keywords,
                "hashtags": self.hashtags,
            },
            "email_subjects": self.email_subjects,
        }


CONTENT_SYSTEM_PROMPT = """You are YAHAVIS Content Engine — world-class content strategist,
copywriter, and SEO expert. Generate complete, high-quality content packages.
Be bold, specific, and action-oriented. Write for Indian + global audiences.
Never use generic filler — every sentence must add value."""

BLOG_PROMPT = """Write a comprehensive, SEO-optimized blog post about: "{title}"

TONE: {tone}
TARGET: Indian tech/entrepreneur audience
LENGTH: 800-1200 words

STRUCTURE:
- Hook opening (problem-agitate-solution format)
- 4-6 H2 sections with actionable content
- Each section has 2-3 paragraphs
- Practical examples and actionable takeaways
- Strong CTA at the end

Write the full blog post now:"""

SOCIAL_PROMPT = """For the topic: "{title}"

Write exactly 3 social media captions:

1. TWITTER/X (max 280 chars, punchy, hooks, no hashtags in text):

2. LINKEDIN (3-4 sentences, professional insight, ends with question or CTA):

3. INSTAGRAM (story-style, 3-4 sentences, conversational, emoji-friendly):

Separate each with a blank line. Start each with the platform name."""

SEO_PROMPT = """For the topic: "{title}"

Generate:
1. META TITLE (max 60 chars, include primary keyword):
2. META DESCRIPTION (max 155 chars, compelling, includes CTA):
3. LSI KEYWORDS (5 related terms, comma-separated):
4. HASHTAGS (10 hashtags, mix popular + niche, space-separated with #):
5. EMAIL SUBJECTS (5 subject lines — mix curiosity/urgency/benefit/question/number):

Format exactly as numbered above."""


class ContentEngine:
    """
    Generate complete content packages from a single title input.
    Integrates with YAHAVIS brain for AI generation.
    """

    def __init__(self, brain=None):
        self.brain = brain

    async def generate(
        self,
        title: str,
        content_type: str = "blog",
        tone: str = "professional",
        platform: str = "general",
    ) -> ContentPackage:
        """
        Generate a complete content package for the given title.
        content_type: 'blog' | 'product' | 'social' | 'email' | 'rap'
        """
        log.info(f"Generating content: '{title}' [{content_type}, {tone}]")
        pkg = ContentPackage(title=title, tone=tone)

        if content_type == "rap":
            pkg.blog_post = await self._generate_rap(title)
            return pkg

        if content_type in ("blog", "general"):
            blog_task    = asyncio.create_task(self._generate_blog(title, tone))
            social_task  = asyncio.create_task(self._generate_social(title))
            seo_task     = asyncio.create_task(self._generate_seo(title))
            email_task   = asyncio.create_task(self._generate_email_subjects(title))

            pkg.blog_post = await blog_task
            social = await social_task
            seo    = await seo_task
            pkg.email_subjects = await email_task

            pkg.twitter    = social.get("twitter", "")
            pkg.linkedin   = social.get("linkedin", "")
            pkg.instagram  = social.get("instagram", "")
            pkg.meta_title       = seo.get("meta_title", title[:60])
            pkg.meta_description = seo.get("meta_description", "")
            pkg.keywords   = seo.get("keywords", [])
            pkg.hashtags   = seo.get("hashtags", [])

        elif content_type == "product":
            pkg.blog_post = await self._generate_product_desc(title)
            pkg.twitter   = await self._generate_promo_post(title, "twitter")
            pkg.instagram = await self._generate_promo_post(title, "instagram")

        elif content_type == "email":
            pkg.blog_post = await self._generate_email_campaign(title)

        elif content_type == "youtube":
            pkg.blog_post = await self._generate_youtube_script(title)

        log.info(f"Content package ready: {len(pkg.blog_post)} chars")
        return pkg

    async def _think(self, prompt: str) -> str:
        if not self.brain:
            return f"[Content placeholder for: {prompt[:50]}...]"
        return await self.brain.think(
            prompt,
            extra_system=CONTENT_SYSTEM_PROMPT,
            use_context=False,
        )

    async def _generate_blog(self, title: str, tone: str) -> str:
        return await self._think(BLOG_PROMPT.format(title=title, tone=tone))

    async def _generate_social(self, title: str) -> dict:
        raw = await self._think(SOCIAL_PROMPT.format(title=title))
        return self._parse_social(raw)

    async def _generate_seo(self, title: str) -> dict:
        raw = await self._think(SEO_PROMPT.format(title=title))
        return self._parse_seo(raw)

    async def _generate_email_subjects(self, title: str) -> list:
        prompt = (
            f"Write 5 compelling email subject lines for: '{title}'\n"
            f"Mix: curiosity / urgency / benefit / question / number format.\n"
            f"Output ONLY the 5 subjects, one per line, no numbers or bullets."
        )
        raw = await self._think(prompt)
        return [line.strip() for line in raw.strip().split("\n") if line.strip()][:5]

    async def _generate_product_desc(self, name: str) -> str:
        prompt = (
            f"Write a compelling WooCommerce product description for: '{name}'\n"
            f"Brand: Hackknow (Indian cybersecurity + tech tools)\n"
            f"2-3 paragraphs: benefits, features, CTA. Bold important phrases."
        )
        return await self._think(prompt)

    async def _generate_promo_post(self, name: str, platform: str) -> str:
        limits = {"twitter": 280, "instagram": 400, "linkedin": 600}
        prompt = (
            f"Write a {platform} promotional post for product: '{name}'\n"
            f"Max {limits.get(platform, 300)} chars. Include relevant emojis. "
            f"End with a strong CTA. Brand: Hackknow."
        )
        return await self._think(prompt)

    async def _generate_email_campaign(self, subject: str) -> str:
        prompt = (
            f"Write a 3-email drip campaign sequence about: '{subject}'\n"
            f"Email 1: Welcome/Problem awareness\n"
            f"Email 2: Solution/Value\n"
            f"Email 3: CTA/Offer\n"
            f"Each email: Subject line + Body (200-300 words). Brand: Hackknow."
        )
        return await self._think(prompt)

    async def _generate_youtube_script(self, title: str) -> str:
        prompt = (
            f"Write a complete YouTube video script for: '{title}'\n"
            f"Sections: HOOK (15 sec) → INTRO (30 sec) → MAIN CONTENT (5-7 min) "
            f"→ OUTRO + CTA (30 sec)\n"
            f"Include [VISUAL CUE] notes. Conversational, engaging, Indian audience."
        )
        return await self._think(prompt)

    async def _generate_rap(self, topic: str) -> str:
        prompt = (
            f"Write a Hindi rap verse about: '{topic}'\n"
            f"Style: Gritty, ambitious, real — like Myth from Hackknow.\n"
            f"2 verses + 1 hook. Mix Hindi and English naturally.\n"
            f"Themes: hustle, tech, building from zero, India pride."
        )
        return await self._think(prompt)

    def _parse_social(self, raw: str) -> dict:
        result = {"twitter": "", "linkedin": "", "instagram": ""}
        lines = raw.strip().split("\n")
        current = None
        buffer = []
        for line in lines:
            line_lower = line.lower()
            if "twitter" in line_lower or "x:" in line_lower:
                if current and buffer:
                    result[current] = " ".join(buffer).strip()
                current, buffer = "twitter", []
            elif "linkedin" in line_lower:
                if current and buffer:
                    result[current] = " ".join(buffer).strip()
                current, buffer = "linkedin", []
            elif "instagram" in line_lower:
                if current and buffer:
                    result[current] = " ".join(buffer).strip()
                current, buffer = "instagram", []
            elif current and line.strip():
                buffer.append(line.strip())
        if current and buffer:
            result[current] = " ".join(buffer).strip()
        return result

    def _parse_seo(self, raw: str) -> dict:
        result = {
            "meta_title": "", "meta_description": "",
            "keywords": [], "hashtags": [], "email_subjects": []
        }
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if "meta title" in low or low.startswith("1."):
                result["meta_title"] = line.split(":", 1)[-1].strip()[:60]
            elif "meta desc" in low or low.startswith("2."):
                result["meta_description"] = line.split(":", 1)[-1].strip()[:155]
            elif "keyword" in low or low.startswith("3."):
                kw_str = line.split(":", 1)[-1].strip()
                result["keywords"] = [k.strip() for k in kw_str.split(",")][:5]
            elif "hashtag" in low or low.startswith("4."):
                ht_str = line.split(":", 1)[-1].strip()
                result["hashtags"] = [h.strip() for h in ht_str.split() if h.startswith("#")][:10]
        return result
