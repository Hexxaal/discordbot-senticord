require('dotenv').config();
const express = require('express');
const session = require('express-session');
const passport = require('passport');
const DiscordStrategy = require('passport-discord').Strategy;
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

passport.use(new DiscordStrategy({
  clientID: process.env.DISCORD_CLIENT_ID,
  clientSecret: process.env.DISCORD_CLIENT_SECRET,
  callbackURL: process.env.REDIRECT_URI,
  scope: ['identify', 'guilds']
}, (accessToken, refreshToken, profile, done) => done(null, profile)));

app.use(session({
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false
}));
app.use(passport.initialize());
app.use(passport.session());

passport.serializeUser((user, done) => done(null, user));
passport.deserializeUser((obj, done) => done(null, obj));

app.get('/auth/login', passport.authenticate('discord'));
app.get('/auth/callback',
  passport.authenticate('discord', { failureRedirect: '/' }),
  (req, res) => res.redirect(`/guilds/${req.user.guilds[0].id}`)
);

function checkAdmin(req, res, next) {
  // TODO: verify req.user owns guild and has admin_role
  next();
}

app.use(express.json());

app.get('/guilds/:id', checkAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'client', 'build', 'index.html'));
});

app.get('/api/guilds/:id/settings', checkAdmin, (req, res) => {
  // TODO: read from SQLite and return JSON
});

app.post('/api/guilds/:id/settings', checkAdmin, (req, res) => {
  // TODO: write to SQLite and return JSON
});

app.listen(PORT, () => console.log(`Panel running on ${PORT}`));
