export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: September 3, 2026</p>

        <div className="space-y-6 text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Information We Collect</h2>
            <p>When you use LinkForge, we collect:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li><strong>Account information:</strong> email address, name, and password (stored securely using Argon2 hashing).</li>
              <li><strong>URL data:</strong> short links you create, original URLs, custom aliases, and expiration settings.</li>
              <li><strong>Analytics data:</strong> click counts, geographic location (country/city), device type, browser, referrer, and UTM parameters.</li>
              <li><strong>Usage data:</strong> IP addresses for rate limiting and security, and audit logs of actions taken within workspaces.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">2. How We Use Your Information</h2>
            <ul className="list-disc ml-6 space-y-1">
              <li>To provide and maintain the LinkForge URL shortening service.</li>
              <li>To display analytics and click statistics to workspace members.</li>
              <li>To send transactional emails (email verification, password resets, workspace invitations).</li>
              <li>To detect and prevent abuse, fraud, and unauthorized access.</li>
              <li>To improve our service and user experience.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">3. Data Sharing</h2>
            <p>We do not sell or rent your personal information to third parties. We may share data with:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li><strong>Infrastructure providers:</strong> Vercel (hosting), Neon (database), MongoDB Atlas (analytics storage), Upstash (Redis caching), Render (backend hosting).</li>
              <li><strong>OAuth providers:</strong> Google and GitHub for authentication, only when you choose to sign in with them.</li>
              <li><strong>When required by law:</strong> if legally obligated to comply with a valid legal request.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">4. Data Security</h2>
            <p>We implement industry-standard security measures including HTTPS encryption, httpOnly cookies for authentication tokens, Argon2 password hashing, and rate limiting. However, no method of electronic transmission is 100% secure.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">5. Data Retention</h2>
            <p>Account data is retained until you delete your account. Soft-deleted URLs are permanently removed after 30 days. Analytics data is retained indefinitely unless you delete the associated URLs.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">6. Your Rights</h2>
            <ul className="list-disc ml-6 space-y-1">
              <li>You can access, update, or delete your account from the settings page.</li>
              <li>You can delete your URLs at any time.</li>
              <li>You can request account deletion by contacting us.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">7. Cookies</h2>
            <p>LinkForge uses httpOnly session cookies for authentication. These cookies are essential for the service to function and are not used for tracking or advertising.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">8. Changes to This Policy</h2>
            <p>We may update this policy from time to time. Continued use of LinkForge after changes constitutes acceptance of the updated policy.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">9. Contact</h2>
            <p>For questions about this privacy policy, contact us at <strong>ram.atchutratna@gmail.com</strong>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
