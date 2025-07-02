require('dotenv').config();
const express  = require('express');
const session  = require('express-session');
const passport = require('passport');
const DiscordStrategy = require('passport-discord').Strategy;
const path     = require('path');

const app  = express();
const PORT = process.env.PORT || 3000;

// 1) Serve React’s build directory as static
const buildPath = path.join(__dirname, 'client', 'build');
app.use(express.static(buildPath));

// 2) Standard middleware (sessions, passport, body parsing, etc.)
app.use(session({
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false
}));
app.use(passport.initialize());
app.use(passport.session());
app.use(express.json());

// 3) OAuth2 routes (login, callback) remain here…
passport.use(new DiscordStrategy({
  clientID:     process.env.DISCORD_CLIENT_ID,
  clientSecret: process.env.DISCORD_CLIENT_SECRET,
  callbackURL:  process.env.REDIRECT_URI,
  scope:        ['identify','guilds']
}, (accessToken, refreshToken, profile, done) => done(null, profile)));

passport.serializeUser((u, done) => done(null, u));
passport.deserializeUser((o, done) => done(null, o));

app.get('/auth/login', passport.authenticate('discord'));
app.get('/auth/callback',
  passport.authenticate('discord',{ failureRedirect:'/' }),
  (req, res) => res.redirect(`/guilds/${req.user.guilds[0].id}`)
);

// 4) Your API routes (e.g. GET/POST /api/guilds/:id/settings) go here…

// … after app.use(express.static(buildPath))

// JSON body parsing + sessions + passport already set up above…

// ─── OAuth2 LOGIN & CALLBACK ────────────────────────────────────
app.get('/auth/login', passport.authenticate('discord'));

app.get(
  '/auth/callback',
  passport.authenticate('discord', { failureRedirect: '/' }),
  (req, res) => {
    // On successful login, redirect into your panel
    const guildId = req.user.guilds[0].id;
    res.redirect(`/guilds/${guildId}`);
  }
);

// ─── SETTINGS API ───────────────────────────────────────────────
// Return the current settings for a guild as JSON
app.get('/api/guilds/:id/settings', checkAdmin, (req, res) => {
  const cfg = getSettingsFromSQLite(req.params.id);
  res.json(cfg);
});

// Save updated settings from the React UI
app.post('/api/guilds/:id/settings', checkAdmin, (req, res) => {
  const { adminRole, logChannel, /* any other fields */ } = req.body;
  saveSettingsToSQLite(req.params.id, adminRole, logChannel);
  res.json({ success: true });
});
// Middleware to check if user is admin
function checkAdmin(req, res, next) {
  if (!req.isAuthenticated() || !req.user.guilds.some(g => g.id === req.params.id && g.permissions.includes('ADMINISTRATOR'))) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  next();
}

// 5) Panel UI route – always serve index.html for /guilds/:id
app.get('/guilds/:id', (req, res) => {
  res.sendFile(path.join(buildPath, 'index.html'));
});

// 6) Fallback: any other path (e.g. static assets, deep React routes)
app.get('*', (req, res) => {
  res.sendFile(path.join(buildPath, 'index.html'));
});

// 7) Start up
app.listen(PORT, () => console.log(`Panel running on port ${PORT}`));
