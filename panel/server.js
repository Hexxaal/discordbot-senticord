require('dotenv').config();
const express = require('express');
const passport = require('passport');
const session  = require('express-session');
const DiscordStrategy = require('passport-discord').Strategy;
const { get_settings, set_settings } = require('./db-utils'); // your SQLite helpers

const app = express();
const PORT = 3000;

// Middleware
app.use(express.json());
app.use(session({ secret: process.env.SESSION_SECRET, resave:false, saveUninitialized:false }));
app.use(passport.initialize());
app.use(passport.session());

// OAuth2
passport.use(new DiscordStrategy({
  clientID: process.env.DISCORD_CLIENT_ID,
  clientSecret: process.env.DISCORD_CLIENT_SECRET,
  callbackURL: process.env.REDIRECT_URI,
  scope: ['identify','guilds']
}, (accessToken, refreshToken, profile, done) => done(null, profile)));

passport.serializeUser((u, done)=>done(null,u));
passport.deserializeUser((o, done)=>done(null,o));

function checkAuth(req,res,next){
  if (req.isAuthenticated()) return next();
  res.redirect('/auth/login');
}

function checkAdmin(req,res,next){
  // Only allow owner OR role in settings.admin_role
  const guildId = req.params.id;
  const cfg = get_settings(guildId);
  const user = req.user;
  // owner?
  const meGuild = user.guilds.find(g => g.id===guildId);
  if (meGuild && meGuild.owner) return next();
  // or has role?
  // you’ll need to fetch member roles via the Bot token if cfg.admin_role
  // (implement as needed)
  return next(); // adjust with real logic
}

app.get('/auth/login', passport.authenticate('discord'));
app.get('/auth/callback',
  passport.authenticate('discord',{ failureRedirect:'/' }),
  (req,res) => {
    const gid = req.user.guilds[0].id;
    // now redirect to Nginx-served static panel:
    res.redirect(`/guilds/${gid}`);
  }
);

// API
app.get('/api/guilds/:id/settings', checkAuth, checkAdmin, (req,res)=>{
  const cfg = get_settings(req.params.id);
  res.json(cfg);
});

app.post('/api/guilds/:id/settings', checkAuth, checkAdmin, (req,res)=>{
  const { admin_role, log_channel } = req.body;
  set_settings(req.params.id, admin_role, log_channel);
  res.json({ success: true });
});

app.listen(PORT, ()=>console.log(`API listening on ${PORT}`));
