// js/index.js
require("dotenv").config();
const { Client, GatewayIntentBits, Partials } = require("discord.js");

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMessageReactions,
  ],
  partials: [Partials.Message, Partials.Reaction],
});

// On ready
client.once("ready", () => {
  console.log(`JS Helper online as ${client.user.tag}`);
});

// Example: auto-delete NSFW images in non-NSFW channels
client.on("messageCreate", async (msg) => {
  if (msg.author.bot || !msg.attachments.size) return;
  if (!msg.channel.nsfw) {
    for (const att of msg.attachments.values()) {
      if (/\.(jpg|jpeg|png|gif)$/i.test(att.url)) {
        await msg.delete();
        await msg.channel.send(
          `${msg.author}, images are not allowed here. Please respect channel rules.`
        );
        break;
      }
    }
  }
});

// Reaction-role example
client.on("messageReactionAdd", async (reaction, user) => {
  if (user.bot) return;
  // suppose you have a message ID to watch
  const ROLE_MSG_ID = process.env.ROLE_MSG_ID;
  if (reaction.message.id === ROLE_MSG_ID && reaction.emoji.name === "👍") {
    const guild = reaction.message.guild;
    const member = guild.members.cache.get(user.id);
    const role = guild.roles.cache.find((r) => r.name === "Member");
    if (member && role) member.roles.add(role);
  }
});

client.login(process.env.DISCORD_TOKEN);
