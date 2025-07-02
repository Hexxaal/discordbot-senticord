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
