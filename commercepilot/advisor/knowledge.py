"""Version-controlled facts about the shipped platform; never marketing promises."""

GUIDES = [
    {"title": "Business information", "route": "/business", "description": "Create a client workspace and save niche, target location/audience, currency and campaign budget. You can ask for guidance before creating one."},
    {"title": "Product Hunter", "route": "/products", "description": "Search live product listings, compare candidates, add a product manually or import from Shopify. A listing is not proof of demand; confirm supplier costs and select a product."},
    {"title": "Store Architect", "route": "/store", "description": "Generate and edit storefront copy/design and export an HTML draft. Review claims and set up a working commerce platform and checkout separately."},
    {"title": "Marketing Studio", "route": "/marketing", "description": "Create campaign objectives, creative ideas, copy, test budgets and allocation drafts. Review the plan before publishing externally. This integration does not buy or publish ads."},
    {"title": "Business Analytics", "route": "/analytics", "description": "Review deterministic unit economics, supply actual measurements and explicit scenario assumptions. Missing costs and measurements remain unknown."},
    {"title": "Connections & AI", "route": "/settings", "description": "Verify the configured model, connect a Shopify Admin token for catalog import, and connect Meta with ads_read for read-only account reporting. Secrets are held on the server."},
    {"title": "Customer Support", "route": "/support", "description": "Sync published Shopify products and policies, add FAQs, configure a shopper-facing chat widget and copy its installation code. Policy sync requires read_legal_policies; catalog sync requires read_products."},
    {"title": "Project History", "route": "/history", "description": "Reopen saved workspaces. Separate client instances are needed for unrelated clients."},
]
WELCOME = "Welcome to CommercePilot. I can explain each section, help you shape a business idea and build a practical budget around your niche, location and audience. Tell me what you want to sell and the budget you have—or ask where to start."
BOUNDARIES = {
    "ads": "Marketing Studio drafts campaigns. Meta access is read-only reporting; ad publication and spending are not implemented. Never claim ads were launched or promise guaranteed sales/ROAS.",
    "advice": "Recommend relevant platform steps on their merits. Explain pros and cons, cash reserves and when not to advertise. Do not pressure the user, invent urgency, request debt or discourage comparison.",
    "finance": "Budget shares are planning assumptions. Use the server's calculations; no invented costs, local rates, FX, taxes, demand statistics or investment/loan advice. Ask for missing figures and distinguish evidence from hypotheses.",
    "privacy": "Business advice chat is separate from the Shopify shopper widget. Sign-in remains deferred and the deployment is a shared workspace. Never expose keys or unrelated projects.",
}
