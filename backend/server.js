// Express API stub for Senticord
const express = require('express');
const session = require('express-session');
const passport = require('passport');
require('./routes/auth')(passport);
const app = express();
app.use(express.json());
app.use(session({ secret: process.env.SESSION_SECRET, resave: false, saveUninitialized: false }));
app.use(passport.initialize());
app.use(passport.session());
app.use('/api/auth', require('./routes/auth'));
app.use('/api/servers', require('./routes/servers'));
app.listen(3000, () => console.log('API listening on port 3000'));
