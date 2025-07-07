# Senticord

Super-Admin Discord bot in Python + JS  
Features:
- CAPTCHA on join
- Reaction roles
- Spam/flood detection & auto-moderation
- NSFW channel checks
- Custom slash commands

## Structure

- `main.py` — Python bot (captcha, spam-filter, welcome, role assign)
- `js/index.js` — JS bot (reaction roles, advanced dashboard, optional LLM calls)
- `Procfile` — Heroku / container entrypoint
