# Senticord - Discord Bot

## Structure

- `ansible/roles`: Contains `api`, `webpanel`, `bot` roles for deployment.
- `commands`: Python command modules.
- `panel`: Static frontend files.
- `bot.py`, `utils.py`: Core bot logic.
- `backend`: Express API for OAuth2 and server data.
- `frontend`: React panel source.

## Deployment

Use Ansible to deploy all components:

```bash
ansible-playbook ansible/site.yml -i ansible/inventories
```
