const { createProxyMiddleware } = require('http-proxy-middleware');

/**
 * @description Configures a manual proxy for the Create React App development server.
 * This file is automatically detected by React Scripts. It tells the development
 * server to only proxy requests that start with '/api' to the backend Flask server.
 * All other requests (like for static assets or hot-reloading files) will be
 * handled by the development server itself, fixing the ECONNREFUSED error.
 */
module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:5001',
      changeOrigin: true,
    })
  );
};
