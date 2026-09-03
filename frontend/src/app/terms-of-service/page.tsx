export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: September 3, 2026</p>

        <div className="space-y-6 text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Acceptance of Terms</h2>
            <p>By accessing or using LinkForge, you agree to be bound by these Terms of Service. If you do not agree, do not use the service.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">2. Description of Service</h2>
            <p>LinkForge is a URL shortening platform that provides link management, click analytics, team workspaces, and webhook integrations.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">3. User Accounts</h2>
            <ul className="list-disc ml-6 space-y-1">
              <li>You must be at least 13 years old to create an account.</li>
              <li>You are responsible for maintaining the security of your account.</li>
              <li>You must not share your account credentials with others.</li>
              <li>One person may not maintain more than one free account.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">4. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>Create links to malicious, phishing, or illegal content.</li>
              <li>Use the service for spam, abuse, or distribution of malware.</li>
              <li>Attempt to circumvent rate limits or security measures.</li>
              <li>Use automated tools to create excessive numbers of links.</li>
              <li>Resell or redistribute the service without authorization.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">5. Content and Links</h2>
            <p>You retain ownership of the URLs you shorten. LinkForge does not take ownership of your content. You are solely responsible for the legality and safety of the destinations your links point to.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">6. Service Availability</h2>
            <p>We strive to maintain high availability but do not guarantee uninterrupted service. We may perform maintenance or suspend service with reasonable notice.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">7. Limitation of Liability</h2>
            <p>LinkForge is provided &quot;as is&quot; without warranties of any kind. We are not liable for any indirect, incidental, or consequential damages arising from your use of the service.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">8. Termination</h2>
            <p>We reserve the right to suspend or terminate accounts that violate these terms. You may delete your account at any time from the settings page.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">9. Changes to Terms</h2>
            <p>We may update these terms at any time. Continued use after changes constitutes acceptance. We will notify users of material changes via email.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">10. Contact</h2>
            <p>For questions about these terms, contact us at <strong>ram.atchutratna@gmail.com</strong>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
