from copy import deepcopy
from textwrap import dedent


SEO_SUPPORTED_LANGS = ("bg", "en", "fr", "ru")


SEO_LANDING_PAGE_ORDER = (
    "/concierge-bulgaria",
    "/property-management-bulgaria",
    "/guest-experience-services",
    "/vacation-rental-operations",
    "/sveti-vlas-concierge-services",
)


def _page(**kwargs):
    return kwargs


_SEO_PAGE_UI_COPY = {
    "en": {
        "related_eyebrow": "Internal links",
        "related_title": "Related BlackSea Connect pages",
        "related_copy": "Use these pages to explore the wider operations model and move from research into action.",
        "next_eyebrow": "Next step",
        "next_title": "See the workflow in a practical operations request.",
        "next_copy": "If you are evaluating the fit for a coastal property, the fastest way to move from reading to action is to request a service workflow or open the demo.",
        "request_service_label": "Request service",
        "view_demo_label": "View demo",
        "footer_description": "Coastal property operations for hospitality teams, guest concierge and trusted local partners.",
        "footer_note": "BlackSea Connect supports coastal hospitality teams with a calm, practical operations workflow.",
    },
    "bg": {
        "related_eyebrow": "Вътрешни връзки",
        "related_title": "Свързани страници на BlackSea Connect",
        "related_copy": "Използвайте тези страници, за да разгледате по-широкия оперативен модел и да преминете от проучване към действие.",
        "next_eyebrow": "Следваща стъпка",
        "next_title": "Вижте работния поток в реална заявка за операции.",
        "next_copy": "Ако преценявате дали решението е подходящо за крайбрежен имот, най-бързият път е да заявите работен поток за услуга или да отворите демото.",
        "request_service_label": "Заявете услуга",
        "view_demo_label": "Вижте демото",
        "footer_description": "Оперативна платформа за крайбрежни имоти, гост-сървиз и доверени местни партньори.",
        "footer_note": "BlackSea Connect помага на екипите по Черноморието с спокоен и практичен оперативен процес.",
    },
    "fr": {
        "related_eyebrow": "Liens internes",
        "related_title": "Pages associées BlackSea Connect",
        "related_copy": "Consultez ces pages pour explorer le modèle opérationnel plus large et passer de la recherche à l’action.",
        "next_eyebrow": "Étape suivante",
        "next_title": "Découvrez le workflow dans une demande opérationnelle concrète.",
        "next_copy": "Si vous évaluez l’adéquation pour un bien côtier, le moyen le plus rapide d’avancer est de demander un workflow de service ou d’ouvrir la démo.",
        "request_service_label": "Demander un service",
        "view_demo_label": "Voir la démo",
        "footer_description": "Plateforme d’exploitation pour les biens côtiers, le guest concierge et les partenaires locaux de confiance.",
        "footer_note": "BlackSea Connect aide les équipes hôtelières du littoral avec un workflow opérationnel calme et pratique.",
    },
    "ru": {
        "related_eyebrow": "Внутренние ссылки",
        "related_title": "Связанные страницы BlackSea Connect",
        "related_copy": "Используйте эти страницы, чтобы изучить более широкий операционный модель и перейти от исследования к действию.",
        "next_eyebrow": "Следующий шаг",
        "next_title": "Посмотрите рабочий процесс в реальном операционном запросе.",
        "next_copy": "Если вы оцениваете решение для прибрежного объекта, самый быстрый путь - запросить рабочий процесс обслуживания или открыть демо.",
        "request_service_label": "Запросить услугу",
        "view_demo_label": "Посмотреть демо",
        "footer_description": "Операционная платформа для прибрежной недвижимости, гостевого сервиса и проверенных местных партнёров.",
        "footer_note": "BlackSea Connect помогает командам на Черном море спокойным и практичным операционным процессом.",
    },
}


SEO_LANDING_PAGES = {
    "/concierge-bulgaria": _page(
        lang="en",
        title="BlackSea Connect | Concierge Services in Bulgaria",
        description="Concierge services in Bulgaria for coastal property teams that need guest arrival coordination, trusted local partners, housekeeping support and a clear service request workflow.",
        canonical_path="/concierge-bulgaria",
        og_type="website",
        h1="Concierge services in Bulgaria for coastal hospitality teams",
        eyebrow="SEO landing page",
        intro="BlackSea Connect helps hospitality teams, property managers and coastal operators bring concierge work into one calm operational flow. Instead of treating guest support as a collection of phone calls and chat messages, the platform connects arrival coordination, housekeeping updates, local partners and service requests into a single workflow that the team can trust. That matters in Bulgaria, where properties move between peak-season intensity and quieter shoulder months, and where guests expect quick answers without feeling the machinery behind the stay.",
        keywords=[
            "concierge services Bulgaria",
            "guest concierge",
            "coastal property operations",
            "trusted local partners",
            "service request workflow",
        ],
        ctas=[
            {"label": "Request concierge support", "href": "/request-service", "class": "button--primary"},
            {"label": "See the services overview", "href": "/services", "class": "button--secondary"},
            {"label": "Explore guest experience", "href": "/guest-experience-services", "class": "button--tertiary"},
        ],
        content_html=dedent(
            """
            <section class="trust-layer" aria-labelledby="concierge-bulgaria-what">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">What concierge means on the coast</p>
                <h2 id="concierge-bulgaria-what">Concierge support should remove friction, not add another inbox.</h2>
              </div>
              <p>On the Black Sea coast, concierge work is rarely just about restaurant bookings or an airport transfer. It is the connective tissue between the guest, the property, and the people who make the stay run smoothly. A late arrival can affect housekeeping, a missed transfer can affect the front desk, and a simple question about Wi-Fi can turn into a poor review if nobody responds quickly. BlackSea Connect gives teams one place to capture that demand and one place to see whether it was resolved.</p>
              <p>The best concierge operations do not rely on memory or informal group chats. They use a consistent process that records who asked, what was promised, who is responsible, and when the follow-up is due. That is especially important in Bulgaria's coastal markets, where properties often serve international travelers, seasonal owners, and repeat guests with very different expectations. When the workflow is visible, the response feels personal to the guest and manageable to the team.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="concierge-bulgaria-services">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Service scope</p>
                <h2 id="concierge-bulgaria-services">A concierge workflow that covers the full guest journey.</h2>
              </div>
              <p>BlackSea Connect is designed around the tasks that coastal hospitality teams actually handle every day. That includes guest arrival coordination, housekeeping coordination, trusted local partners, and the service request workflow that keeps special asks from slipping through the cracks. If a guest needs a private driver, a last-minute cleaning change, a grocery delivery, or help with a marina transfer, the request can move through the same operational pathway instead of being handled in a separate, fragile thread.</p>
              <p>The platform is also useful for properties that operate across several towns and need a consistent standard of care. Teams can route a request to the right person, see the status at a glance, and keep the guest updated without asking them to repeat the same details. That consistency matters for guest concierge, but it also matters for property managers who need a reliable record of what was requested, what was completed, and what still needs attention.</p>
              <ul>
                <li>Guest arrival coordination for airport, marina, and private car transfers.</li>
                <li>Housekeeping coordination for turnovers, inspections, and last-minute adjustments.</li>
                <li>Trusted local partners for maintenance, laundry, drivers, and specialist support.</li>
                <li>Service request workflow that keeps each task visible until it is resolved.</li>
              </ul>
            </section>

            <section class="trust-layer" aria-labelledby="concierge-bulgaria-workflow">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Operational workflow</p>
                <h2 id="concierge-bulgaria-workflow">From guest request to resolution, the team stays in control.</h2>
              </div>
              <p>A practical concierge system starts with a clear intake. The team needs to know whether the request came from the guest portal, a phone call, a message at check-in, or an owner note. Once the request is logged, it can be assigned, tagged, and timed without losing the context that made it important. That reduces the risk of duplicate work and makes it easier to move fast when the request touches multiple teams, such as housekeeping and transport.</p>
              <p>For Bulgarian coastal properties, this workflow also helps seasonal teams stay aligned. During peak months, a concierge may handle dozens of small requests that look trivial in isolation but matter a great deal to the guest experience. In quieter periods, the same process gives owners and managers better visibility into recurring issues and common service patterns. The result is a concierge service that feels premium externally and disciplined internally, which is the balance modern hospitality operations need.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="concierge-bulgaria-fit">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Why BlackSea Connect</p>
                <h2 id="concierge-bulgaria-fit">Built for teams that need trusted local partners and fewer handoffs.</h2>
              </div>
              <p>Many hospitality teams start with a spreadsheet or a messaging app and only later discover that the service demand has outgrown the tool. BlackSea Connect is meant to solve that gap without forcing a redesign of the business. It keeps the tone of the guest interaction calm, but it gives the operator enough structure to manage service levels, partner coordination, and follow-up with confidence. That combination is valuable when the property portfolio spans more than one city or when the team works with different providers across the coast.</p>
              <p>If you are comparing concierge services in Bulgaria, the real question is whether the service can scale without becoming noisy. BlackSea Connect is designed to keep the work legible, keep the guest informed, and keep the owner or manager confident that the request will be handled. For teams researching coastal property operations, the best next step is often to review the <a href="/guest-experience-services">guest experience services</a> page, compare it with <a href="/property-management-bulgaria">property management in Bulgaria</a>, and then decide whether to <a href="/request-service">request a service workflow</a> or explore the <a href="/demo/operations">operations demo</a>.</p>
            </section>

            <section class="trust-layer" aria-labelledby="concierge-bulgaria-faq">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Frequently asked questions</p>
                <h2 id="concierge-bulgaria-faq">Common questions about concierge services in Bulgaria.</h2>
              </div>
              <div class="trust-grid">
                <article class="trust-card">
                  <h3>Does concierge support only matter for luxury properties?</h3>
                  <p>No. Any property that wants faster responses, cleaner handoffs, and a better guest experience can benefit from a concierge workflow, whether it is a villa, apartment building, or boutique hotel.</p>
                </article>
                <article class="trust-card">
                  <h3>Can concierge tasks include housekeeping and transfers?</h3>
                  <p>Yes. The strongest hospitality operations connect concierge work to housekeeping coordination and guest arrival coordination so that one request can move through the whole stay without being lost.</p>
                </article>
                <article class="trust-card">
                  <h3>Is this useful for teams working only part of the year?</h3>
                  <p>Absolutely. Seasonal teams often need more structure than permanent teams because handoffs change quickly, and a repeatable service request workflow helps keep standards consistent.</p>
                </article>
              </div>
            </section>
            """
        ).strip(),
        related_links=[
            {"href": "/property-management-bulgaria", "label": "Property management in Bulgaria", "description": "See how the platform supports owners, operations and maintenance across a coastal portfolio."},
            {"href": "/guest-experience-services", "label": "Guest experience services", "description": "Learn how arrival coordination and in-stay support shape the guest journey."},
            {"href": "/request-service", "label": "Request a service workflow", "description": "Capture a request and route it through the operations team with a clear process."},
            {"href": "/services", "label": "Core services overview", "description": "Review the broader BlackSea Connect operations platform and its service model."},
        ],
        service_schema={
            "@context": "https://schema.org",
            "@type": "Service",
            "name": "Concierge services in Bulgaria",
            "url": "https://blackseaconnect.com/concierge-bulgaria",
            "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
            "areaServed": "Bulgaria",
            "serviceType": [
                "coastal property operations",
                "guest concierge",
                "guest arrival coordination",
                "housekeeping coordination",
            ],
            "description": "Concierge services in Bulgaria for coastal property teams that need guest arrival coordination, trusted local partners, housekeeping support and a clear service request workflow.",
        },
    ),
    "/property-management-bulgaria": _page(
        lang="en",
        title="BlackSea Connect | Property Management Bulgaria for Coastal Teams",
        description="Property management in Bulgaria for coastal operators who need housekeeping coordination, guest arrival coordination, maintenance tracking and trusted local partners in one platform.",
        canonical_path="/property-management-bulgaria",
        og_type="website",
        h1="Property management in Bulgaria for coastal portfolios",
        eyebrow="SEO landing page",
        intro="Property management in Bulgaria looks different when the assets are coastal. Turnovers are tighter, guest arrivals are more time sensitive, maintenance is often seasonal, and owner expectations can change quickly with occupancy. BlackSea Connect is built to help operators manage those moving parts without losing sight of the guest. It gives teams a calmer way to handle housekeeping coordination, transfer coordination, local partner dispatch and service requests so that the portfolio feels organized even when the calendar is full.",
        keywords=[
            "property management Bulgaria",
            "coastal property operations",
            "housekeeping coordination",
            "guest arrival coordination",
            "trusted local partners",
        ],
        ctas=[
            {"label": "Explore property operations", "href": "/services", "class": "button--primary"},
            {"label": "See the network directory", "href": "/network", "class": "button--secondary"},
            {"label": "Request a service workflow", "href": "/request-service", "class": "button--tertiary"},
        ],
        content_html=dedent(
            """
            <section class="trust-layer" aria-labelledby="pm-bulgaria-context">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">The reality of coastal property management</p>
                <h2 id="pm-bulgaria-context">Property management in Bulgaria needs more than a checklist.</h2>
              </div>
              <p>Coastal portfolios are shaped by seasonality, travel patterns, and the pace of guest turnover. A property manager may have to coordinate cleaning teams, check-in windows, maintenance visits, and owner reporting all in the same afternoon. BlackSea Connect provides a system for that kind of work: a place to capture the request, a place to assign it, and a place to see the status without chasing updates across multiple channels. The result is a more reliable property operation and a better guest experience.</p>
              <p>For teams operating villas, apartment buildings, and short-stay units along the Black Sea coast, the challenge is not just task volume. It is consistency. One property can have an excellent handoff while another struggles with late turnover or unclear responsibility. By keeping the operational flow visible, BlackSea Connect helps managers build repeatable standards across the portfolio, which is essential when owners expect professional hospitality operations and guests expect hotel-level responsiveness.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="pm-bulgaria-scope">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Operational scope</p>
                <h2 id="pm-bulgaria-scope">The core work of a coastal property manager.</h2>
              </div>
              <p>Property management is often described in broad terms, but in practice it is a sequence of small decisions. Which unit needs an inspection? Which arrival needs a transfer update? Which maintenance issue should be handled before the next guest lands? BlackSea Connect is designed to keep those decisions in view. Teams can centralize guest arrival coordination, housekeeping coordination, and service requests so that the manager is not the only person who knows what matters next.</p>
              <p>The platform also helps with trusted local partners. When the right person is already known for a specific task, the team can move quickly without sacrificing accountability. That matters in Bulgaria because many portfolios rely on a small network of reliable drivers, cleaners, maintenance specialists and concierge contacts. The goal is not to replace local knowledge. The goal is to make that knowledge easier to use, easier to hand off, and easier to measure.</p>
              <ul>
                <li>Coordinate check-in, turnover and inspection timing across multiple properties.</li>
                <li>Track maintenance, housekeeping and guest service requests in one workflow.</li>
                <li>Manage trusted local partners without losing notes or context between teams.</li>
                <li>Provide owners with a calmer operating picture and more consistent standards.</li>
              </ul>
            </section>

            <section class="trust-layer" aria-labelledby="pm-bulgaria-portfolio">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Portfolio control</p>
                <h2 id="pm-bulgaria-portfolio">A better way to oversee villas, apartments and mixed portfolios.</h2>
              </div>
              <p>Owners do not just want activity. They want confidence that the activity is well run. BlackSea Connect gives property managers a way to show that the work has been planned, assigned and completed. That is especially useful when a portfolio spans different building types or multiple towns along the coast, where each site may have its own rhythm and operational risks. The platform keeps each property legible without asking the team to maintain a separate process for every building.</p>
              <p>It also supports the transition from reactive management to proactive management. A team that can see patterns in service requests, housekeeping timing, or transfer delays can make better decisions about staffing and partner selection. Over time that creates a stronger operating model, fewer repeat failures, and a guest experience that feels more polished. For managers looking beyond one-off fixes, this is where hospitality operations start to scale without becoming chaotic.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="pm-bulgaria-why">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Why teams adopt it</p>
                <h2 id="pm-bulgaria-why">The platform helps the team stay calm while the portfolio keeps moving.</h2>
              </div>
              <p>BlackSea Connect is useful because it respects the realities of field operations. Teams still need to talk to guests, coordinate with cleaners, and negotiate with suppliers. What changes is the amount of structure around that work. Instead of relying on memory, the team can use a service request workflow that records the conversation, surfaces the next step, and helps everyone know when the task is finished. That structure reduces friction and improves accountability without making the operation feel bureaucratic.</p>
              <p>If you are exploring property management in Bulgaria for coastal assets, it helps to compare the platform with the <a href="/vacation-rental-operations">vacation rental operations</a> page, the <a href="/concierge-bulgaria">concierge services in Bulgaria</a> page, and the main <a href="/services">services overview</a>. Those pages show how the same system supports different parts of the guest lifecycle. When you are ready to see it in a real workflow, you can <a href="/request-service">request a service</a> or review the <a href="/demo/operations">operations demo</a>.</p>
            </section>

            <section class="trust-layer" aria-labelledby="pm-bulgaria-faq">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Frequently asked questions</p>
                <h2 id="pm-bulgaria-faq">Property management questions from coastal operators.</h2>
              </div>
              <div class="trust-grid">
                <article class="trust-card">
                  <h3>Does this replace our existing property manager?</h3>
                  <p>No. It supports the manager by keeping coordination, guest requests and partner work visible across the operation.</p>
                </article>
                <article class="trust-card">
                  <h3>Can it work across villas and apartments together?</h3>
                  <p>Yes. The platform is designed for mixed coastal portfolios that need one operational pattern and different property-specific notes.</p>
                </article>
                <article class="trust-card">
                  <h3>Is it helpful during the off-season?</h3>
                  <p>Very much so. Quiet months are ideal for improving workflows, reviewing service patterns and preparing the next high season.</p>
                </article>
              </div>
            </section>
            """
        ).strip(),
        related_links=[
            {"href": "/vacation-rental-operations", "label": "Vacation rental operations", "description": "See the model for multi-unit portfolios, turnovers and repeatable operating standards."},
            {"href": "/concierge-bulgaria", "label": "Concierge services in Bulgaria", "description": "Understand how guest support and local partners fit into the property operation."},
            {"href": "/guest-experience-services", "label": "Guest experience services", "description": "Explore the guest-facing side of the same coastal operations platform."},
            {"href": "/network", "label": "Approved provider network", "description": "Browse the trusted local partner directory that powers the workflow."},
        ],
        service_schema={
            "@context": "https://schema.org",
            "@type": "Service",
            "name": "Property management in Bulgaria",
            "url": "https://blackseaconnect.com/property-management-bulgaria",
            "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
            "areaServed": "Bulgaria",
            "serviceType": [
                "coastal property operations",
                "property management",
                "housekeeping coordination",
                "guest arrival coordination",
            ],
            "description": "Property management in Bulgaria for coastal operators who need housekeeping coordination, guest arrival coordination, maintenance tracking and trusted local partners in one platform.",
        },
    ),
    "/guest-experience-services": _page(
        lang="en",
        title="BlackSea Connect | Guest Experience Services for Hospitality Teams",
        description="Guest experience services for hospitality teams that want better arrivals, clearer communication, smoother stays and a practical service request workflow.",
        canonical_path="/guest-experience-services",
        og_type="website",
        h1="Guest experience services that make the stay feel effortless",
        eyebrow="SEO landing page",
        intro="Guest experience is often described as a feeling, but behind that feeling is a sequence of operational decisions. Was the arrival clear? Did housekeeping finish on time? Did the guest know who to contact when something changed? BlackSea Connect helps hospitality teams manage those moments with a calmer workflow that connects guest arrival coordination, concierge support, trusted local partners and service request handling. The goal is to make the stay feel simple from the outside while keeping the operation fully in control on the inside.",
        keywords=[
            "guest experience services",
            "guest arrival coordination",
            "hospitality operations platform",
            "guest concierge",
            "service request workflow",
        ],
        ctas=[
            {"label": "See guest portal examples", "href": "/guest/a-302", "class": "button--primary"},
            {"label": "Review services", "href": "/services", "class": "button--secondary"},
            {"label": "Request support", "href": "/request-service", "class": "button--tertiary"},
        ],
        content_html=dedent(
            """
            <section class="trust-layer" aria-labelledby="guest-experience-journey">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">The guest journey</p>
                <h2 id="guest-experience-journey">Guest experience starts before arrival and continues after departure.</h2>
              </div>
              <p>Great hospitality operations do not begin at the front door. They begin when the guest books, asks a question, requests a transfer or opens the guest portal. At that point the team already needs to know the property, the timing, the language preference and the likely service needs. BlackSea Connect makes that context part of the operational record so the guest does not have to repeat themselves as the conversation moves from planning to check-in to in-stay support.</p>
              <p>That matters because guests judge the quality of a stay by the ease of the small things. If the arrival is smooth, the instructions are clear, and the support is responsive, they feel cared for even before they meet anyone in person. The platform gives teams a way to coordinate those details consistently, which helps create the kind of hospitality that feels premium without feeling forced.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="guest-experience-touchpoints">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Key touchpoints</p>
                <h2 id="guest-experience-touchpoints">The moments that shape a memorable stay.</h2>
              </div>
              <p>Guest experience services work best when they cover the full lifecycle of a stay. That means pre-arrival communication, arrival timing, housekeeping readiness, on-property support and departure follow-up. BlackSea Connect keeps those touchpoints in one workflow so the team can see where the guest is in the journey and what still needs attention. It is especially valuable when a single service touches multiple people, such as a transfer that affects both a driver and a housekeeping team.</p>
              <p>The same approach also helps with special requests. Guests may ask for restaurant recommendations, equipment delivery, late checkout, a private driver, or help with a local issue. Those requests should not disappear into a generic inbox. They should be visible, assignable and easy to close. When that happens, the guest feels seen and the operation stays efficient. That is why guest experience services are not just about communication. They are about coordination.</p>
              <ul>
                <li>Guest arrival coordination for seamless check-in and transfer timing.</li>
                <li>Housekeeping coordination so the property is ready when the guest expects it.</li>
                <li>Concierge support for recommendations, reservations and local assistance.</li>
                <li>Service request workflow that keeps every ask visible until completed.</li>
              </ul>
            </section>

            <section class="trust-layer" aria-labelledby="guest-experience-operations">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Operational design</p>
                <h2 id="guest-experience-operations">Operations matter because the guest should never have to think about them.</h2>
              </div>
              <p>When operations are fragmented, the guest notices. When they are connected, the guest simply feels supported. BlackSea Connect is built around that principle. It gives hospitality teams a clear system for updates, ownership and follow-through, which is especially useful in coastal markets where the same property might be serving families, couples, owners and business travelers in the same month. Each group brings different expectations, but the operational baseline should stay consistent.</p>
              <p>The platform also supports the team behind the scenes. A calmer operational workflow means fewer repeated questions, fewer missed handoffs and fewer last-minute surprises. That gives staff more time to focus on the human part of hospitality: tone, timing and attention. If you are building a guest-facing service model for coastal properties, the most valuable technology is the kind that disappears into the experience while making the staff more effective.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="guest-experience-differentiator">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Why it stands out</p>
                <h2 id="guest-experience-differentiator">A guest experience platform should be practical for the team and invisible to the guest.</h2>
              </div>
              <p>That balance is what BlackSea Connect is designed to deliver. It keeps the language of hospitality front and center, but it gives the operator enough structure to run the work properly. That means guest experience services are not just a marketing phrase. They become a repeatable part of the operation, connected to housekeeping, local partners and request handling. For properties with repeated arrivals, that consistency becomes a real brand advantage.</p>
              <p>To see how the same workflow extends into other parts of the stay, review <a href="/concierge-bulgaria">concierge services in Bulgaria</a>, <a href="/vacation-rental-operations">vacation rental operations</a>, and the <a href="/guest/a-302">guest portal example</a>. Those pages show how the platform supports the stay from different angles, while the <a href="/demo/operations">operations demo</a> makes the coordination model easier to visualize. If you want to turn guest experience into a reliable system, the next step is to <a href="/request-service">request a service workflow</a> that matches your property.</p>
            </section>

            <section class="trust-layer" aria-labelledby="guest-experience-faq">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Frequently asked questions</p>
                <h2 id="guest-experience-faq">Questions hospitality teams ask when improving the guest journey.</h2>
              </div>
              <div class="trust-grid">
                <article class="trust-card">
                  <h3>Is guest experience only about guest communication?</h3>
                  <p>No. Communication matters, but the quality of the stay is usually decided by timing, coordination and follow-through behind the scenes.</p>
                </article>
                <article class="trust-card">
                  <h3>Can guest experience services support multiple property types?</h3>
                  <p>Yes. The same workflow can work across villas, apartments and boutique hospitality properties with different operational rhythms.</p>
                </article>
                <article class="trust-card">
                  <h3>Does the platform help with recurring requests?</h3>
                  <p>Yes. Repeated requests become easier to spot, route and resolve, which helps the team improve the guest experience over time.</p>
                </article>
              </div>
            </section>
            """
        ).strip(),
        related_links=[
            {"href": "/concierge-bulgaria", "label": "Concierge services in Bulgaria", "description": "See the concierge workflow that supports guest support and local coordination."},
            {"href": "/property-management-bulgaria", "label": "Property management in Bulgaria", "description": "Connect the guest journey with the wider operating model for a coastal portfolio."},
            {"href": "/guest/a-302", "label": "Guest portal example", "description": "Preview a live guest-facing experience built for arrivals and support."},
            {"href": "/services", "label": "Services overview", "description": "Review the complete BlackSea Connect operations platform."},
        ],
        service_schema={
            "@context": "https://schema.org",
            "@type": "Service",
            "name": "Guest experience services",
            "url": "https://blackseaconnect.com/guest-experience-services",
            "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
            "areaServed": "Black Sea coast",
            "serviceType": [
                "guest experience services",
                "guest arrival coordination",
                "guest concierge",
                "service request workflow",
            ],
            "description": "Guest experience services for hospitality teams that want better arrivals, clearer communication, smoother stays and a practical service request workflow.",
        },
    ),
    "/vacation-rental-operations": _page(
        lang="en",
        title="BlackSea Connect | Vacation Rental Operations for Coastal Portfolios",
        description="Vacation rental operations for coastal portfolios that need housekeeping coordination, guest arrival coordination, transfer management and trusted local partners at scale.",
        canonical_path="/vacation-rental-operations",
        og_type="website",
        h1="Vacation rental operations built for coastal scale",
        eyebrow="SEO landing page",
        intro="Vacation rental operations are easy to underestimate until a portfolio starts growing. What began as a few properties quickly becomes a chain of turnovers, guest arrivals, housekeeping checks, transfer questions and owner updates. BlackSea Connect is built for that stage of growth. It brings the operational pieces together so that each stay is supported by a clear process instead of a frantic scramble. For coastal portfolios, that means fewer surprises, better guest communication and a more reliable way to coordinate local partners.",
        keywords=[
            "vacation rental operations",
            "housekeeping coordination",
            "guest arrival coordination",
            "coastal property operations",
            "trusted local partners",
        ],
        ctas=[
            {"label": "See the demo flow", "href": "/demo/operations", "class": "button--primary"},
            {"label": "Browse providers", "href": "/network", "class": "button--secondary"},
            {"label": "Request service", "href": "/request-service", "class": "button--tertiary"},
        ],
        content_html=dedent(
            """
            <section class="trust-layer" aria-labelledby="vacation-rental-scale">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Scaling without losing control</p>
                <h2 id="vacation-rental-scale">A growing portfolio needs a repeatable operating system.</h2>
              </div>
              <p>As vacation rental operations expand, the risks change. A single missed turnover can affect a chain of arrivals. A transfer delay can cascade into housekeeping rescheduling. A maintenance issue can create a review problem if it is not handled quickly. BlackSea Connect gives operators the structure to keep those moving parts visible, which makes it easier to protect service quality as the portfolio grows. That is especially important on the coast, where demand can spike quickly and the team may be serving multiple properties in the same day.</p>
              <p>The platform is designed to support the operational work, not hide it. Teams can keep the request path clear, assign responsibility, and track what happens next without relying on informal memory. That helps vacation rental managers move from reactive problem-solving to a more predictable standard of care. The more properties you manage, the more valuable that repeatability becomes, because it protects both the guest experience and the owner's confidence in the operation.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="vacation-rental-core">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Core workflows</p>
                <h2 id="vacation-rental-core">Housekeeping, arrivals and service requests are the heartbeat of the portfolio.</h2>
              </div>
              <p>Vacation rental operations usually succeed or fail in the details. A clean turnover is not just a checklist item; it is a promise that the next guest can trust. An on-time transfer is not just logistics; it sets the tone for the whole stay. BlackSea Connect keeps those basics organized through housekeeping coordination, guest arrival coordination and service request workflow tools that give the team a clearer picture of what is happening right now and what still needs to be done.</p>
              <p>The same system helps with trusted local partners. Many coastal portfolios depend on a network of cleaners, drivers, maintenance vendors and concierge contacts. When those relationships are managed informally, the team spends too much time asking who can help. When they are managed inside a structured workflow, the team can move faster and with more confidence. That allows the manager to focus on the guest and the owner instead of chasing the process.</p>
              <ul>
                <li>Coordinate checkouts, turnovers and same-day arrivals with fewer handoff mistakes.</li>
                <li>Track housekeeping coordination across units, buildings and different season schedules.</li>
                <li>Dispatch trusted local partners for transfer support and urgent maintenance.</li>
                <li>Use one service request workflow for guests, owners and internal teams.</li>
              </ul>
            </section>

            <section class="trust-layer" aria-labelledby="vacation-rental-owners">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Owner confidence</p>
                <h2 id="vacation-rental-owners">Owners want visibility, not just activity.</h2>
              </div>
              <p>One of the biggest challenges in vacation rental operations is translating daily work into something owners can understand. Owners want to know that the property is being looked after, but they do not need a stream of fragmented updates. BlackSea Connect helps the operator organize the underlying work so that owner communication can be simpler, more accurate and more trustworthy. That is valuable in coastal markets where occupancy changes quickly and the team has to react without losing professionalism.</p>
              <p>The platform also supports better planning. If the team can see which requests repeat, which properties require more attention, and which partners are consistently reliable, management can improve staffing and make better decisions about the portfolio. Over time that becomes a strategic advantage. The operation is not only handling more work; it is learning from the work and becoming more resilient as a result.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="vacation-rental-growth">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Why BlackSea Connect works</p>
                <h2 id="vacation-rental-growth">The platform supports growth without making the operation feel heavy.</h2>
              </div>
              <p>Many tools promise automation but create more work for the people using them. BlackSea Connect is intentionally practical. It keeps the experience calm, the workflow clear and the service model easy to explain. That makes it a good fit for hospitality teams that need better operations but do not want to rebuild their brand voice or their guest experience. It is equally useful for individual managers and for small teams supporting multiple coastal properties.</p>
              <p>If your focus is vacation rental operations, the most useful next steps are to compare this page with <a href="/property-management-bulgaria">property management in Bulgaria</a>, <a href="/concierge-bulgaria">concierge services in Bulgaria</a>, and the <a href="/services">core services page</a>. You can also review the <a href="/network">approved provider network</a> to understand how the partner layer fits into the workflow. When you are ready to see the system in motion, the <a href="/demo/operations">operations demo</a> gives a clear picture of how the work is coordinated.</p>
            </section>

            <section class="trust-layer" aria-labelledby="vacation-rental-faq">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Frequently asked questions</p>
                <h2 id="vacation-rental-faq">Questions from operators scaling coastal vacation rentals.</h2>
              </div>
              <div class="trust-grid">
                <article class="trust-card">
                  <h3>Is this only for large portfolios?</h3>
                  <p>No. The same workflow can help a single operator or a growing portfolio because the problem is coordination, not size alone.</p>
                </article>
                <article class="trust-card">
                  <h3>Does it help with same-day turnovers?</h3>
                  <p>Yes. Same-day turnover is one of the best use cases for structured housekeeping coordination and visible task ownership.</p>
                </article>
                <article class="trust-card">
                  <h3>Can it reduce guest-facing delays?</h3>
                  <p>Yes. Clearer arrival coordination and better partner dispatch usually reduce the small delays that create the biggest guest frustration.</p>
                </article>
              </div>
            </section>
            """
        ).strip(),
        related_links=[
            {"href": "/property-management-bulgaria", "label": "Property management in Bulgaria", "description": "Learn how to keep a coastal portfolio organized and visible."},
            {"href": "/guest-experience-services", "label": "Guest experience services", "description": "See how the guest journey connects to the back-office workflow."},
            {"href": "/network", "label": "Provider network", "description": "Find approved local partners that can help support the operation."},
            {"href": "/demo/operations", "label": "Operations demo", "description": "Watch the platform’s workflow in a calm, practical interface."},
        ],
        service_schema={
            "@context": "https://schema.org",
            "@type": "Service",
            "name": "Vacation rental operations",
            "url": "https://blackseaconnect.com/vacation-rental-operations",
            "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
            "areaServed": "Black Sea coast",
            "serviceType": [
                "vacation rental operations",
                "housekeeping coordination",
                "guest arrival coordination",
                "trusted local partners",
            ],
            "description": "Vacation rental operations for coastal portfolios that need housekeeping coordination, guest arrival coordination, transfer management and trusted local partners at scale.",
        },
    ),
    "/sveti-vlas-concierge-services": _page(
        lang="en",
        title="BlackSea Connect | Sveti Vlas Concierge Services",
        description="Sveti Vlas concierge services for coastal properties near the marina, beachfront apartments and hillside villas that need reliable guest support and local coordination.",
        canonical_path="/sveti-vlas-concierge-services",
        og_type="website",
        h1="Sveti Vlas concierge services for coastal properties and marina stays",
        eyebrow="SEO landing page",
        intro="Sveti Vlas concierge services need to understand the local rhythm of the town. Guests arrive through the marina, through seaside roads, and through apartment complexes that serve families, yacht travelers and repeat visitors. BlackSea Connect helps operators in Sveti Vlas coordinate guest arrival timing, housekeeping, local partners and in-stay requests in a way that feels organized and premium. The result is a smoother operation for properties close to the water, the hillside, and the busy seasonal promenades.",
        keywords=[
            "Sveti Vlas concierge services",
            "guest concierge",
            "Black Sea property management",
            "guest arrival coordination",
            "trusted local partners",
        ],
        ctas=[
            {"label": "Request Sveti Vlas support", "href": "/request-service", "class": "button--primary"},
            {"label": "Explore concierge services", "href": "/concierge-bulgaria", "class": "button--secondary"},
            {"label": "See approved partners", "href": "/network", "class": "button--tertiary"},
        ],
        content_html=dedent(
            """
            <section class="trust-layer" aria-labelledby="sveti-vlas-local">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Local hospitality context</p>
                <h2 id="sveti-vlas-local">Sveti Vlas is a place where concierge work meets a very specific coastal rhythm.</h2>
              </div>
              <p>Unlike a generic resort page, Sveti Vlas concierge services need to reflect the actual movement of the town: the marina traffic, the beachfront pace, the seasonality, and the expectations of guests who may arrive by car, by transfer, or by boat. BlackSea Connect helps teams manage that variety without making the guest feel the complexity behind the scenes. Arrival coordination, housekeeping updates and partner dispatch all happen inside a single operational workflow.</p>
              <p>That matters because Sveti Vlas often serves a mixed audience. Some guests want a quiet family stay, others want easy access to restaurants and the waterfront, and some need a more premium concierge layer that can handle reservations, transport and last-minute adjustments. A property operation that can handle those differences gracefully creates a stronger reputation and fewer avoidable problems. The platform makes the workflow visible so the team can respond with confidence.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="sveti-vlas-guest-needs">
              <div class="section-heading">
                <p class="section-heading__eyebrow">What guests need</p>
                <h2 id="sveti-vlas-guest-needs">The most common requests in Sveti Vlas are operational, not decorative.</h2>
              </div>
              <p>In a coastal location, the small details can dominate the guest experience. A delayed transfer can change the start of the stay. A late housekeeping finish can affect the check-in window. A missed local recommendation can make the guest feel disconnected from the destination. BlackSea Connect keeps those moments organized through a service request workflow that can route the task to the right person and ensure it stays visible until it is done.</p>
              <p>The town also benefits from a trusted local partner layer. Drivers, cleaners, maintenance teams and concierge contacts all have a role to play in keeping the stay smooth. When those partners are coordinated through a structured workflow, the property team is less likely to lose track of a request or repeat the same explanation twice. That creates a more reliable experience for guests visiting Sveti Vlas for the marina, the beach or the relaxed Black Sea atmosphere.</p>
              <ul>
                <li>Guest arrival coordination for marina arrivals, private drivers and late check-ins.</li>
                <li>Housekeeping coordination for beach apartments, hillside villas and mixed-use units.</li>
                <li>Concierge support for dining, transport, reservations and destination guidance.</li>
                <li>Trusted local partners who can step in when timing matters and response speed counts.</li>
              </ul>
            </section>

            <section class="trust-layer" aria-labelledby="sveti-vlas-operations">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Operational advantage</p>
                <h2 id="sveti-vlas-operations">The best Sveti Vlas concierge services make the property feel composed.</h2>
              </div>
              <p>Guests do not usually see the coordination layer, but they feel its effect immediately. When the arrival is timed well, the property is ready, and the local support is responsive, the stay feels composed. BlackSea Connect helps deliver that composure by keeping the operational process visible to the team and by making the next action obvious. This is the kind of discipline that supports premium hospitality operations without becoming rigid or impersonal.</p>
              <p>The platform is also useful for teams managing properties that are slightly different from one another. A marina-facing apartment might need a different transfer pattern from a hillside villa, while a family-focused stay may need clearer instructions and more immediate response to questions. The same system can support those differences while preserving a common standard. That makes it easier to train staff, use trusted local partners effectively, and keep guest experience consistent across the portfolio.</p>
            </section>

            <section class="credibility-layer" aria-labelledby="sveti-vlas-research">
              <div class="section-heading">
                <p class="section-heading__eyebrow">Why this page exists</p>
                <h2 id="sveti-vlas-research">Searchers looking for Sveti Vlas concierge services want a practical answer.</h2>
              </div>
              <p>This page is intentionally focused on Sveti Vlas because location-specific search intent matters. Visitors searching for concierge services in Sveti Vlas are usually not looking for a generic hospitality slogan. They want to understand whether the service can support real properties, real arrivals and real operations in the town they know. BlackSea Connect addresses that by connecting the local context to a broader coastal property management model that also works across Bulgaria.</p>
              <p>If you are evaluating the fit, it helps to compare this page with <a href="/concierge-bulgaria">concierge services in Bulgaria</a>, <a href="/property-management-bulgaria">property management in Bulgaria</a>, and <a href="/guest-experience-services">guest experience services</a>. Those pages show how the same platform supports different parts of the stay. You can also review the <a href="/network">approved provider network</a> or open the <a href="/demo/operations">operations demo</a> to see how the system handles the handoffs that matter most in a coastal town like Sveti Vlas.</p>
            </section>

            <section class="trust-layer" aria-labelledby="sveti-vlas-faq">
              <div class="section-heading section-heading--trust">
                <p class="section-heading__eyebrow">Frequently asked questions</p>
                <h2 id="sveti-vlas-faq">Questions from property teams and hosts in Sveti Vlas.</h2>
              </div>
              <div class="trust-grid">
                <article class="trust-card">
                  <h3>Can this support properties near the marina?</h3>
                  <p>Yes. Marina arrivals often need careful timing and reliable partner coordination, which is exactly what the workflow is designed to support.</p>
                </article>
                <article class="trust-card">
                  <h3>Is it useful for hillside villas and apartments?</h3>
                  <p>Yes. Different property types can use the same operational model while keeping their own notes, timing and service needs.</p>
                </article>
                <article class="trust-card">
                  <h3>Does it help with seasonal guest demand?</h3>
                  <p>Yes. Seasonal demand is easier to manage when requests, partners and handoffs are visible in a single service request workflow.</p>
                </article>
              </div>
            </section>
            """
        ).strip(),
        related_links=[
            {"href": "/concierge-bulgaria", "label": "Concierge services in Bulgaria", "description": "Read the broader concierge strategy for Black Sea hospitality teams."},
            {"href": "/guest-experience-services", "label": "Guest experience services", "description": "See how Sveti Vlas guest support fits into the wider stay experience."},
            {"href": "/property-management-bulgaria", "label": "Property management in Bulgaria", "description": "Connect the local property operation with the full portfolio workflow."},
            {"href": "/request-service", "label": "Request support", "description": "Start a service request and route it through the operational workflow."},
        ],
        service_schema={
            "@context": "https://schema.org",
            "@type": "Service",
            "name": "Sveti Vlas concierge services",
            "url": "https://blackseaconnect.com/sveti-vlas-concierge-services",
            "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
            "areaServed": "Sveti Vlas",
            "serviceType": [
                "Sveti Vlas concierge services",
                "guest concierge",
                "guest arrival coordination",
                "trusted local partners",
            ],
            "description": "Sveti Vlas concierge services for coastal properties near the marina, beachfront apartments and hillside villas that need reliable guest support and local coordination.",
        },
    ),
}


SEO_LANDING_PAGE_LOCALES = {
    "/concierge-bulgaria": {
        "bg": {
            "title": "BlackSea Connect | Консиерж услуги в България",
            "description": "Консиерж услуги в България за крайбрежни екипи, които имат нужда от координация на пристиганията, доверени местни партньори, housekeeping подкрепа и ясен workflow за заявки за услуги.",
            "h1": "Консиерж услуги в България за крайбрежни хотелиерски екипи",
            "eyebrow": "SEO landing page",
            "intro": "BlackSea Connect помага на хотелиерски екипи, property managers и крайбрежни оператори да подредят консиерж работата в един спокоен оперативен поток. Вместо да се разчита на хаотични обаждания и чатове, платформата свързва координацията на пристиганията, housekeeping обновленията, местните партньори и заявките за услуги в една видима система, на която екипът може да се довери.",
            "keywords": [
                "консиерж услуги България",
                "гост-сървиз",
                "операции за крайбрежни имоти",
                "доверени местни партньори",
                "workflow за заявки за услуги",
            ],
            "ctas": [
                {"label": "Заявете консиерж подкрепа", "href": "/request-service", "class": "button--primary"},
                {"label": "Вижте услугите", "href": "/services", "class": "button--secondary"},
                {"label": "Разгледайте гост-сървиз", "href": "/guest-experience-services", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="concierge-bulgaria-what">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Какво означава консиерж на брега</p>
                    <h2 id="concierge-bulgaria-what">Консиерж подкрепата трябва да маха триенето, а не да добавя нова поща.</h2>
                  </div>
                  <p>По Черноморието консиерж работата рядко е само за резервации или трансфери. Тя е връзката между госта, имота и хората, които правят престоя гладък. Закъсняло пристигане може да обърка housekeeping, пропуснат трансфер може да натовари рецепцията, а бавен отговор по Wi-Fi може да се превърне в лошо ревю. BlackSea Connect дава на екипа едно място, където заявката се вижда от началото до затварянето ѝ.</p>
                  <p>Най-добрите консиерж операции не разчитат на памет или неформални чатове. Те използват последователен процес, който записва кой е попитал, какво е обещано, кой отговаря и кога трябва да има follow-up. Това е особено важно в българските крайбрежни пазари, където имотите обслужват международни гости, сезонни собственици и редовни посетители с различни очаквания.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="concierge-bulgaria-services">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Обхват на услугата</p>
                    <h2 id="concierge-bulgaria-services">Консиерж workflow, който покрива целия гостски път.</h2>
                  </div>
                  <p>BlackSea Connect е създаден около задачите, които крайбрежните екипи реално изпълняват всеки ден: координация на пристиганията, housekeeping, доверени местни партньори и workflow за заявки за услуги. Ако гостът има нужда от шофьор, късна промяна на почистването, доставка на хранителни продукти или помощ с трансфер до марина, заявката минава по същия оперативен път.</p>
                  <p>Платформата е полезна и за имоти, които работят в повече от един град. Екипът може да маршрутизира заявката към правилния човек, да вижда статуса на момента и да държи госта информиран, без той да повтаря едно и също. Това е важно за гост-сървиза, но и за property managers, които искат надежден запис за това какво е било поискано, какво е завършено и какво остава.</p>
                  <ul>
                    <li>Координация на пристиганията за летищни, марина и частни трансфери.</li>
                    <li>Housekeeping координация за turnovers, инспекции и промени в последния момент.</li>
                    <li>Доверени местни партньори за поддръжка, пране, шофьори и специализирана помощ.</li>
                    <li>Workflow за заявки за услуги, който държи всяка задача видима до нейното приключване.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="concierge-bulgaria-workflow">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Оперативен поток</p>
                    <h2 id="concierge-bulgaria-workflow">От заявката на госта до приключването, екипът запазва контрол.</h2>
                  </div>
                  <p>Практичният concierge системи започва с ясен intake. Екипът трябва да знае дали заявката идва от guest portal, телефонно обаждане, съобщение при настаняване или бележка от собственик. След като заявката е записана, тя може да бъде assign-ната, тагната и проследена без да се губи контекстът, който я прави важна.</p>
                  <p>За българските крайбрежни имоти този поток помага и на сезонните екипи. В пиковите месеци един консиерж може да обработва десетки малки заявки, които сами по себе си изглеждат дребни, но силно влияят на гостското преживяване. В по-тихите периоди същият процес дава на мениджърите по-добра видимост към повтарящи се проблеми и модели на обслужване.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="concierge-bulgaria-fit">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Защо BlackSea Connect</p>
                    <h2 id="concierge-bulgaria-fit">Създаден за екипи, които имат нужда от доверени партньори и по-малко handoffs.</h2>
                  </div>
                  <p>Много хотелиерски екипи започват със spreadsheet или чат и едва по-късно разбират, че service demand е надраснал инструмента. BlackSea Connect решава този gap, без да променя начина, по който бизнесът работи. Той държи тона към госта спокоен, но дава на оператора достатъчно структура за service levels, partner coordination и follow-up.</p>
                  <p>Ако сравнявате консиерж услуги в България, истинският въпрос е дали процесът може да се мащабира без да става шумен. BlackSea Connect е проектиран да поддържа работата ясна, госта информиран и мениджъра уверен, че заявката ще бъде изпълнена.</p>
                </section>

                <section class="trust-layer" aria-labelledby="concierge-bulgaria-faq">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Често задавани въпроси</p>
                    <h2 id="concierge-bulgaria-faq">Чести въпроси за консиерж услугите в България.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Консиерж подкрепата важи ли само за луксозни имоти?</h3>
                      <p>Не. Всеки имот, който иска по-бързи отговори, по-чисти handoffs и по-добро гостско преживяване, може да спечели от консиерж workflow.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Могат ли задачите да включват housekeeping и трансфери?</h3>
                      <p>Да. Най-силните hospitality operations свързват консиерж работата с housekeeping координация и guest arrival координация, за да не се губят заявки.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Полезно ли е за екипи, които работят само сезонно?</h3>
                      <p>Абсолютно. Сезонните екипи имат най-голяма полза от повторяем процес, защото handoffs се променят бързо, а ясният workflow пази стандартите стабилни.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/property-management-bulgaria", "label": "Управление на имоти в България", "description": "Вижте как платформата поддържа собственици, операции и поддръжка на крайбрежен портфейл."},
                {"href": "/guest-experience-services", "label": "Услуги за гостско преживяване", "description": "Научете как пристигането и подкрепата по време на престоя оформят изживяването."},
                {"href": "/request-service", "label": "Заявете workflow за услуга", "description": "Въведете заявка и я насочете през оперативния екип с ясен процес."},
                {"href": "/services", "label": "Преглед на основните услуги", "description": "Разгледайте по-широката BlackSea Connect платформа за операции."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Консиерж услуги в България",
                "url": "https://blackseaconnect.com/concierge-bulgaria",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "България",
                "serviceType": [
                    "coastal property operations",
                    "guest concierge",
                    "guest arrival coordination",
                    "housekeeping coordination",
                ],
                "description": "Консиерж услуги в България за крайбрежни имоти, които имат нужда от координация на пристиганията, housekeeping подкрепа, доверени местни партньори и ясен workflow за заявки за услуги.",
            },
        },
        "fr": {
            "title": "BlackSea Connect | Services de conciergerie en Bulgarie",
            "description": "Services de conciergerie en Bulgarie pour les équipes de biens côtiers qui ont besoin de coordination des arrivées, de partenaires locaux de confiance, de support housekeeping et d’un workflow clair de demandes de service.",
            "h1": "Services de conciergerie en Bulgarie pour les équipes hôtelières côtières",
            "eyebrow": "Page SEO",
            "intro": "BlackSea Connect aide les équipes hôtelières, les property managers et les opérateurs côtiers à regrouper le travail de conciergerie dans un flux opérationnel calme. Au lieu de dépendre d’appels et de conversations dispersées, la plateforme relie la coordination des arrivées, les mises à jour housekeeping, les partenaires locaux et les demandes de service dans un seul workflow lisible.",
            "keywords": [
                "services de conciergerie Bulgarie",
                "guest concierge",
                "opérations de biens côtiers",
                "partenaires locaux de confiance",
                "workflow de demandes de service",
            ],
            "ctas": [
                {"label": "Demander un support conciergerie", "href": "/request-service", "class": "button--primary"},
                {"label": "Voir les services", "href": "/services", "class": "button--secondary"},
                {"label": "Explorer l’expérience client", "href": "/guest-experience-services", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="concierge-bulgaria-what">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Ce que signifie la conciergerie sur la côte</p>
                    <h2 id="concierge-bulgaria-what">Le support conciergerie doit supprimer les frictions, pas créer une nouvelle boîte mail.</h2>
                  </div>
                  <p>Sur la côte de la mer Noire, la conciergerie ne se limite presque jamais aux réservations de restaurant ou aux transferts aéroport. Elle relie le client, le bien et les personnes qui rendent le séjour fluide. Un retard d’arrivée peut perturber le housekeeping, un transfert manqué peut compliquer la réception, et une réponse lente sur le Wi‑Fi peut devenir un mauvais avis.</p>
                  <p>Les meilleures opérations de conciergerie ne reposent ni sur la mémoire ni sur des groupes de discussion informels. Elles utilisent un processus cohérent qui enregistre la demande, la promesse, le responsable et le suivi attendu. C’est particulièrement important dans les marchés côtiers bulgares, où les biens accueillent des voyageurs internationaux, des propriétaires saisonniers et des clients récurrents aux attentes différentes.</p>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/property-management-bulgaria", "label": "Gestion immobilière en Bulgarie", "description": "Découvrez comment la plateforme soutient les opérations et la maintenance d’un portefeuille côtier."},
                {"href": "/guest-experience-services", "label": "Services d’expérience client", "description": "Voyez comment l’arrivée et l’assistance pendant le séjour structurent l’expérience."},
                {"href": "/request-service", "label": "Demander un workflow", "description": "Enregistrez une demande et faites-la circuler dans l’équipe opérationnelle."},
                {"href": "/services", "label": "Aperçu des services", "description": "Explorez la plateforme opérationnelle BlackSea Connect."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Services de conciergerie en Bulgarie",
                "url": "https://blackseaconnect.com/concierge-bulgaria",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Bulgarie",
                "serviceType": [
                    "coastal property operations",
                    "guest concierge",
                    "guest arrival coordination",
                    "housekeeping coordination",
                ],
                "description": "Services de conciergerie en Bulgarie pour les biens côtiers qui ont besoin de coordination des arrivées, de support housekeeping, de partenaires locaux de confiance et d’un workflow clair de demandes de service.",
            },
        },
        "ru": {
            "title": "BlackSea Connect | Консьерж-услуги в Болгарии",
            "description": "Консьерж-услуги в Болгарии для команд прибрежной недвижимости, которым нужна координация прибытия гостей, проверенные местные партнёры, поддержка housekeeping и понятный workflow заявок на услуги.",
            "h1": "Консьерж-услуги в Болгарии для прибрежных гостиничных команд",
            "eyebrow": "SEO-страница",
            "intro": "BlackSea Connect помогает гостиничным командам, управляющим недвижимостью и прибрежным операторам собрать консьерж-работу в спокойный операционный поток. Вместо хаотичных звонков и переписок платформа связывает координацию прибытия, обновления housekeeping, местных партнёров и заявки на услуги в одной понятной системе.",
            "keywords": [
                "консьерж-услуги Болгария",
                "guest concierge",
                "операции прибрежной недвижимости",
                "проверенные местные партнёры",
                "workflow заявок на услуги",
            ],
            "ctas": [
                {"label": "Запросить поддержку консьержа", "href": "/request-service", "class": "button--primary"},
                {"label": "Посмотреть услуги", "href": "/services", "class": "button--secondary"},
                {"label": "Изучить guest experience", "href": "/guest-experience-services", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="concierge-bulgaria-what">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Что означает консьерж на побережье</p>
                    <h2 id="concierge-bulgaria-what">Консьерж-поддержка должна убирать трение, а не добавлять новый inbox.</h2>
                  </div>
                  <p>На Черноморском побережье консьерж-работа редко ограничивается бронированием столика или трансфером из аэропорта. Она соединяет гостя, объект и людей, которые делают пребывание плавным. Позднее прибытие может повлиять на housekeeping, пропущенный трансфер - на ресепшен, а медленный ответ по Wi‑Fi - на отзывы.</p>
                  <p>Лучшие консьерж-операции не полагаются на память или неформальные чаты. Они используют последовательный процесс, который фиксирует запрос, обещание, ответственного и срок follow-up. Это особенно важно на болгарских прибрежных рынках, где объекты принимают международных путешественников, сезонных владельцев и постоянных гостей с разными ожиданиями.</p>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/property-management-bulgaria", "label": "Управление недвижимостью в Болгарии", "description": "Посмотрите, как платформа поддерживает операции и обслуживание прибрежного портфеля."},
                {"href": "/guest-experience-services", "label": "Сервисы guest experience", "description": "Узнайте, как прибытие и поддержка во время проживания формируют впечатление гостя."},
                {"href": "/request-service", "label": "Запросить workflow", "description": "Зафиксируйте запрос и проведите его через операционную команду."},
                {"href": "/services", "label": "Обзор услуг", "description": "Изучите операционную платформу BlackSea Connect."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Консьерж-услуги в Болгарии",
                "url": "https://blackseaconnect.com/concierge-bulgaria",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Болгария",
                "serviceType": [
                    "coastal property operations",
                    "guest concierge",
                    "guest arrival coordination",
                    "housekeeping coordination",
                ],
                "description": "Консьерж-услуги в Болгарии для прибрежной недвижимости, которой нужна координация прибытия, поддержка housekeeping, проверенные местные партнёры и понятный workflow заявок на услуги.",
            },
        },
    },
    "/property-management-bulgaria": {
        "bg": {
            "title": "BlackSea Connect | Управление на имоти в България за крайбрежни екипи",
            "description": "Управление на имоти в България за крайбрежни оператори, които имат нужда от housekeeping координация, guest arrival координация, проследяване на поддръжка и доверени местни партньори в една платформа.",
            "h1": "Управление на имоти в България за крайбрежни портфейли",
            "eyebrow": "SEO landing page",
            "intro": "Управлението на имоти в България изглежда различно, когато активите са крайбрежни. Смените са по-стегнати, пристиганията са по-чувствителни към време, поддръжката често е сезонна, а очакванията на собствениците могат да се променят бързо с заетостта. BlackSea Connect помага на екипите да подредят housekeeping, трансфери, местни партньори и заявки за услуги в един спокоен workflow.",
            "keywords": ["управление на имоти България", "операции за крайбрежни имоти", "housekeeping координация", "guest arrival координация", "доверени местни партньори"],
            "ctas": [
                {"label": "Разгледайте operations", "href": "/services", "class": "button--primary"},
                {"label": "Вижте директорията с партньори", "href": "/network", "class": "button--secondary"},
                {"label": "Заявете workflow", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
        "fr": {
            "title": "BlackSea Connect | Gestion immobilière en Bulgarie pour les équipes côtières",
            "description": "Gestion immobilière en Bulgarie pour les opérateurs côtiers qui ont besoin de coordination housekeeping, de coordination des arrivées, de suivi de maintenance et de partenaires locaux de confiance dans une seule plateforme.",
            "h1": "Gestion immobilière en Bulgarie pour les portefeuilles côtiers",
            "eyebrow": "Page SEO",
            "intro": "La gestion immobilière en Bulgarie change lorsque les actifs sont côtiers. Les turnovers sont plus serrés, les arrivées sont plus sensibles au timing, la maintenance est souvent saisonnière et les attentes des propriétaires évoluent vite avec le taux d’occupation.",
            "keywords": ["gestion immobilière Bulgarie", "opérations de biens côtiers", "coordination housekeeping", "coordination des arrivées", "partenaires locaux de confiance"],
            "ctas": [
                {"label": "Découvrir les opérations", "href": "/services", "class": "button--primary"},
                {"label": "Voir le réseau", "href": "/network", "class": "button--secondary"},
                {"label": "Demander un workflow", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
        "ru": {
            "title": "BlackSea Connect | Управление недвижимостью в Болгарии для прибрежных команд",
            "description": "Управление недвижимостью в Болгарии для прибрежных операторов, которым нужна координация housekeeping, координация прибытия гостей, учёт обслуживания и проверенные местные партнёры в одной платформе.",
            "h1": "Управление недвижимостью в Болгарии для прибрежных портфелей",
            "eyebrow": "SEO-страница",
            "intro": "Управление недвижимостью в Болгарии меняется, когда активы находятся у моря. Смены становятся плотнее, прибытия чувствительнее к времени, обслуживание часто сезонное, а ожидания владельцев быстро меняются вместе с загрузкой.",
            "keywords": ["управление недвижимостью Болгария", "операции прибрежной недвижимости", "координация housekeeping", "координация прибытия гостей", "проверенные местные партнёры"],
            "ctas": [
                {"label": "Изучить operations", "href": "/services", "class": "button--primary"},
                {"label": "Посмотреть сеть", "href": "/network", "class": "button--secondary"},
                {"label": "Запросить workflow", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
    },
    "/guest-experience-services": {
        "bg": {
            "title": "BlackSea Connect | Услуги за guest experience за хотелиерски екипи",
            "description": "Услуги за guest experience за хотелиерски екипи, които искат по-добри пристигания, по-ясна комуникация, по-плавен престой и практичен workflow за заявки.",
            "h1": "Услуги за guest experience, които правят престоя лек",
            "eyebrow": "SEO landing page",
            "intro": "Guest experience често се описва като усещане, но зад това усещане стои последователност от оперативни решения. Дали пристигането е ясно? Дали housekeeping е приключил навреме? Дали гостът знае към кого да се обърне? BlackSea Connect помага на екипите да управляват тези моменти в спокоен workflow.",
            "keywords": ["услуги за guest experience", "guest arrival координация", "hospitality operations platform", "guest concierge", "workflow за заявки"],
            "ctas": [
                {"label": "Вижте примери за guest portal", "href": "/guest/a-302", "class": "button--primary"},
                {"label": "Прегледайте услугите", "href": "/services", "class": "button--secondary"},
                {"label": "Заявете подкрепа", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
        "fr": {
            "title": "BlackSea Connect | Services d’expérience client pour les équipes hôtelières",
            "description": "Services d’expérience client pour les équipes hôtelières qui veulent de meilleures arrivées, une communication plus claire, des séjours plus fluides et un workflow pratique de demandes de service.",
            "h1": "Des services d’expérience client qui rendent le séjour simple",
            "eyebrow": "Page SEO",
            "intro": "L’expérience client est souvent décrite comme un ressenti, mais derrière ce ressenti il y a une suite de décisions opérationnelles. L’arrivée est-elle claire ? Le housekeeping a-t-il terminé à temps ? Le client sait-il à qui s’adresser ?",
            "keywords": ["services d’expérience client", "coordination des arrivées", "plateforme d’opérations hôtelières", "guest concierge", "workflow de demandes"],
            "ctas": [
                {"label": "Voir des exemples de guest portal", "href": "/guest/a-302", "class": "button--primary"},
                {"label": "Consulter les services", "href": "/services", "class": "button--secondary"},
                {"label": "Demander un support", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
        "ru": {
            "title": "BlackSea Connect | Сервисы guest experience для гостиничных команд",
            "description": "Сервисы guest experience для гостиничных команд, которым нужны лучшие прибытия, более понятная коммуникация, более плавное проживание и практичный workflow заявок на услуги.",
            "h1": "Сервисы guest experience, которые делают пребывание лёгким",
            "eyebrow": "SEO-страница",
            "intro": "Guest experience часто описывают как чувство, но за этим чувством стоит последовательность операционных решений. Понятно ли прибытие? Успел ли housekeeping вовремя? Знает ли гость, к кому обратиться?",
            "keywords": ["сервисы guest experience", "координация прибытия гостей", "платформа hospitality operations", "guest concierge", "workflow заявок"],
            "ctas": [
                {"label": "Посмотреть примеры guest portal", "href": "/guest/a-302", "class": "button--primary"},
                {"label": "Открыть услуги", "href": "/services", "class": "button--secondary"},
                {"label": "Запросить поддержку", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
    },
    "/vacation-rental-operations": {
        "bg": {
            "title": "BlackSea Connect | Операции за ваканционни наеми за крайбрежни портфейли",
            "description": "Операции за ваканционни наеми за крайбрежни портфейли, които имат нужда от housekeeping координация, guest arrival координация, transfer management и доверени местни партньори в мащаб.",
            "h1": "Операции за ваканционни наеми, създадени за крайбрежен мащаб",
            "eyebrow": "SEO landing page",
            "intro": "Операциите при ваканционни наеми лесно се подценяват, докато портфейлът не започне да расте. Това, което е било няколко имота, бързо се превръща във верига от turnovers, пристигания, проверки на housekeeping, въпроси за трансфери и отчети към собственици.",
            "keywords": ["операции за ваканционни наеми", "housekeeping координация", "guest arrival координация", "операции за крайбрежни имоти", "доверени местни партньори"],
            "ctas": [
                {"label": "Вижте демо потока", "href": "/demo/operations", "class": "button--primary"},
                {"label": "Разгледайте партньорите", "href": "/network", "class": "button--secondary"},
                {"label": "Заявете услуга", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
        "fr": {
            "title": "BlackSea Connect | Opérations de locations saisonnières pour portefeuilles côtiers",
            "description": "Opérations de locations saisonnières pour portefeuilles côtiers qui ont besoin de coordination housekeeping, de coordination des arrivées, de gestion des transferts et de partenaires locaux de confiance à grande échelle.",
            "h1": "Opérations de locations saisonnières pensées pour l’échelle côtière",
            "eyebrow": "Page SEO",
            "intro": "Les opérations de locations saisonnières sont faciles à sous-estimer jusqu’au moment où le portefeuille commence à grandir. Ce qui était quelques biens devient vite une chaîne de turnovers, d’arrivées, de contrôles housekeeping et de questions de transfert.",
            "keywords": ["opérations locations saisonnières", "coordination housekeeping", "coordination des arrivées", "opérations de biens côtiers", "partenaires locaux de confiance"],
            "ctas": [
                {"label": "Voir la démo", "href": "/demo/operations", "class": "button--primary"},
                {"label": "Parcourir le réseau", "href": "/network", "class": "button--secondary"},
                {"label": "Demander un service", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
        "ru": {
            "title": "BlackSea Connect | Операции vacation rental для прибрежных портфелей",
            "description": "Операции vacation rental для прибрежных портфелей, которым нужна координация housekeeping, координация прибытия гостей, управление трансферами и проверенные местные партнёры в масштабе.",
            "h1": "Операции vacation rental, созданные для прибрежного масштаба",
            "eyebrow": "SEO-страница",
            "intro": "Операции vacation rental легко недооценить, пока портфель не начнёт расти. То, что было несколькими объектами, быстро превращается в цепочку turnovers, прибытия гостей, проверок housekeeping и вопросов по трансферам.",
            "keywords": ["операции vacation rental", "координация housekeeping", "координация прибытия гостей", "операции прибрежной недвижимости", "проверенные местные партнёры"],
            "ctas": [
                {"label": "Посмотреть demo", "href": "/demo/operations", "class": "button--primary"},
                {"label": "Открыть сеть", "href": "/network", "class": "button--secondary"},
                {"label": "Запросить услугу", "href": "/request-service", "class": "button--tertiary"},
            ],
        },
    },
    "/sveti-vlas-concierge-services": {
        "bg": {
            "title": "BlackSea Connect | Консиерж услуги в Свети Влас",
            "description": "Консиерж услуги в Свети Влас за крайбрежни имоти близо до марината, апартаменти на първа линия и вили по хълма, които имат нужда от надеждна гостоприемна подкрепа и локална координация.",
            "h1": "Консиерж услуги в Свети Влас за крайбрежни имоти и марина престои",
            "eyebrow": "SEO landing page",
            "intro": "Консиерж услугите в Свети Влас трябва да разбират локалния ритъм на града. Гостите пристигат през марината, по крайбрежните пътища и през апартаментни комплекси, които обслужват семейства, яхтени пътешественици и редовни посетители.",
            "keywords": ["консиерж услуги Свети Влас", "гост-сървиз", "Black Sea property management", "guest arrival координация", "доверени местни партньори"],
            "ctas": [
                {"label": "Заявете подкрепа за Свети Влас", "href": "/request-service", "class": "button--primary"},
                {"label": "Разгледайте консиерж услугите", "href": "/concierge-bulgaria", "class": "button--secondary"},
                {"label": "Вижте партньорите", "href": "/network", "class": "button--tertiary"},
            ],
        },
        "fr": {
            "title": "BlackSea Connect | Services de conciergerie à Sveti Vlas",
            "description": "Services de conciergerie à Sveti Vlas pour les biens côtiers près de la marina, les appartements en front de mer et les villas sur les hauteurs qui ont besoin d’un support fiable et d’une coordination locale.",
            "h1": "Services de conciergerie à Sveti Vlas pour biens côtiers et séjours marina",
            "eyebrow": "Page SEO",
            "intro": "Les services de conciergerie à Sveti Vlas doivent refléter le rythme local de la ville. Les clients arrivent par la marina, par les routes côtières et par les ensembles résidentiels qui accueillent familles, voyageurs nautiques et visiteurs réguliers.",
            "keywords": ["services de conciergerie Sveti Vlas", "guest concierge", "gestion immobilière mer Noire", "coordination des arrivées", "partenaires locaux de confiance"],
            "ctas": [
                {"label": "Demander un support Sveti Vlas", "href": "/request-service", "class": "button--primary"},
                {"label": "Explorer la conciergerie", "href": "/concierge-bulgaria", "class": "button--secondary"},
                {"label": "Voir les partenaires", "href": "/network", "class": "button--tertiary"},
            ],
        },
        "ru": {
            "title": "BlackSea Connect | Консьерж-услуги в Свети-Власе",
            "description": "Консьерж-услуги в Свети-Власе для прибрежных объектов рядом с мариной, апартаментов у моря и вилл на холмах, которым нужна надёжная поддержка гостей и локальная координация.",
            "h1": "Консьерж-услуги в Свети-Власе для прибрежной недвижимости и марина-пребываний",
            "eyebrow": "SEO-страница",
            "intro": "Консьерж-услуги в Свети-Власе должны отражать местный ритм города. Гости приезжают через марину, по прибрежным дорогам и в апартаментные комплексы, которые принимают семьи, яхтенных путешественников и постоянных гостей.",
            "keywords": ["консьерж-услуги Свети-Влас", "guest concierge", "управление недвижимостью Чёрное море", "координация прибытия", "проверенные местные партнёры"],
            "ctas": [
                {"label": "Запросить поддержку Свети-Влас", "href": "/request-service", "class": "button--primary"},
                {"label": "Изучить консьерж-сервисы", "href": "/concierge-bulgaria", "class": "button--secondary"},
                {"label": "Посмотреть партнёров", "href": "/network", "class": "button--tertiary"},
            ],
        },
    },
}


SEO_LANDING_PAGE_LOCALE_OVERRIDES = {
    "/guest-experience-services": {
        "bg": {
            "title": "BlackSea Connect | Услуги за гостско преживяване",
            "description": "Услуги за гостско преживяване за хотелиерски екипи, които искат по-лесни пристигания, по-ясна комуникация, по-плавен престой и ясен workflow за заявки за услуги.",
            "h1": "Услуги за гостско преживяване, които правят престоя лесен",
            "eyebrow": "SEO landing page",
            "intro": "Гостското преживяване е усещане, но това усещане се изгражда от последователни оперативни решения. Дали пристигането е ясно? Дали housekeeping е готов навреме? Дали гостът знае към кого да се обърне, когато нещо се промени?",
            "keywords": [
                "услуги за гостско преживяване",
                "координация на пристиганията",
                "платформа за хотелски операции",
                "гост-сървиз",
                "workflow за заявки",
            ],
            "ctas": [
                {"label": "Вижте примери за гост-портал", "href": "/guest/a-302", "class": "button--primary"},
                {"label": "Прегледайте услугите", "href": "/services", "class": "button--secondary"},
                {"label": "Заявете подкрепа", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="guest-experience-journey-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Пътят на госта</p>
                    <h2 id="guest-experience-journey-bg">Гостското преживяване започва преди пристигането и продължава след заминаването.</h2>
                  </div>
                  <p>Добрата хотелска операция не започва на входа. Тя започва в момента, в който гостът резервира, зададе въпрос, поиска трансфер или отвори гостския портал. Тогава екипът вече трябва да знае имота, времето, езиковото предпочитание и вероятните нужди.</p>
                  <p>Когато този контекст е част от оперативния запис, гостът не трябва да повтаря едно и също при всяка следваща стъпка. Това прави престоя по-спокоен, а екипа - по-уверен.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="guest-experience-touchpoints-bg">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Ключови моменти</p>
                    <h2 id="guest-experience-touchpoints-bg">Моментите, които оформят запомнящ се престой.</h2>
                  </div>
                  <p>Услугите за гостско преживяване работят най-добре, когато покриват целия престой: преди пристигане, по време на настаняването, при housekeeping готовността, при подкрепата на място и при следващия контакт след заминаването.</p>
                  <p>Същият подход помага и при специални заявки - препоръки, доставки, късно напускане, частен шофьор или местен проблем. Вместо да се губят в обща поща, тези заявки се виждат, разпределят и затварят навреме.</p>
                  <ul>
                    <li>Координация на пристиганията за безпроблемно настаняване и трансфери.</li>
                    <li>Housekeeping координация, така че имотът да е готов когато гостът очаква.</li>
                    <li>Гост-сървиз за препоръки, резервации и локална помощ.</li>
                    <li>Workflow за заявки, който пази всяка заявка видима до приключване.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="guest-experience-ops-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Оперативен дизайн</p>
                    <h2 id="guest-experience-ops-bg">Операциите трябва да работят тихо, за да не ги мисли гостът.</h2>
                  </div>
                  <p>Когато процесите са фрагментирани, гостът го усеща. Когато са свързани, той просто се чувства подкрепен. BlackSea Connect е изграден около тази логика: ясни обновления, ясно ownership и ясно follow-through.</p>
                  <p>Това дава повече време на екипа за онова, което прави гостоприемството премиум - тон, темпо и внимание. Ако изграждате guest-facing модел за крайбрежни имоти, най-ценната технология е тази, която изчезва в преживяването, но прави работата по-лесна.</p>
                </section>

                <section class="trust-layer" aria-labelledby="guest-experience-faq-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Често задавани въпроси</p>
                    <h2 id="guest-experience-faq-bg">Въпроси, които екипите си задават, когато подобряват гостския път.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Гостското преживяване само комуникация ли е?</h3>
                      <p>Не. Комуникацията е важна, но качеството на престоя обикновено се решава от тайминга, координацията и добрия follow-through.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Може ли да работи с различни типове имоти?</h3>
                      <p>Да. Същият workflow работи за вили, апартаменти и бутикови имоти с различен оперативен ритъм.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Помага ли платформата при повтарящи се заявки?</h3>
                      <p>Да. Повтарящите се заявки се виждат по-лесно, насочват се по-бързо и се затварят по-надеждно.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/concierge-bulgaria", "label": "Консиерж услуги в България", "description": "Вижте консиерж workflow-а, който поддържа гостската помощ и локалната координация."},
                {"href": "/property-management-bulgaria", "label": "Управление на имоти в България", "description": "Свържете гостския път с по-широкия оперативен модел за крайбрежен портфейл."},
                {"href": "/guest/a-302", "label": "Пример за гостски портал", "description": "Прегледайте гостско изживяване, създадено за пристигания и помощ на място."},
                {"href": "/services", "label": "Преглед на услугите", "description": "Вижте цялата BlackSea Connect платформа за операции."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Услуги за гостско преживяване",
                "url": "https://blackseaconnect.com/guest-experience-services",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Черноморският бряг",
                "serviceType": [
                    "услуги за гостско преживяване",
                    "координация на пристиганията",
                    "гост-сървиз",
                    "workflow за заявки за услуги",
                ],
                "description": "Услуги за гостско преживяване за хотелиерски екипи, които искат по-добри пристигания, по-ясна комуникация, по-плавен престой и практичен workflow за заявки за услуги.",
            },
        },
        "fr": {
            "title": "BlackSea Connect | Services d’expérience client",
            "description": "Services d’expérience client pour les équipes hôtelières qui veulent des arrivées plus fluides, une communication plus claire, des séjours plus simples et un workflow pratique de demandes de service.",
            "h1": "Des services d’expérience client qui rendent le séjour fluide",
            "eyebrow": "Page SEO",
            "intro": "L’expérience client est une impression, mais cette impression naît de décisions opérationnelles précises. L’arrivée est-elle claire ? Le housekeeping est-il prêt à temps ? Le client sait-il qui contacter si quelque chose change ?",
            "keywords": ["services d’expérience client", "coordination des arrivées", "plateforme d’opérations hôtelières", "guest concierge", "workflow de demandes"],
            "ctas": [
                {"label": "Voir des exemples de guest portal", "href": "/guest/a-302", "class": "button--primary"},
                {"label": "Consulter les services", "href": "/services", "class": "button--secondary"},
                {"label": "Demander un support", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="guest-experience-journey-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Le parcours client</p>
                    <h2 id="guest-experience-journey-fr">L’expérience client commence avant l’arrivée et continue après le départ.</h2>
                  </div>
                  <p>Une bonne opération hôtelière ne commence pas à la porte d’entrée. Elle commence dès la réservation, la première question, la demande de transfert ou l’ouverture du guest portal. À ce moment-là, l’équipe doit déjà connaître le bien, le timing, la langue et les besoins probables.</p>
                  <p>Quand ce contexte est conservé dans le dossier opérationnel, le client n’a pas besoin de répéter les mêmes informations. Le séjour paraît plus simple, et l’équipe travaille avec plus de calme.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="guest-experience-touchpoints-fr">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Points de contact</p>
                    <h2 id="guest-experience-touchpoints-fr">Les moments qui façonnent un séjour mémorable.</h2>
                  </div>
                  <p>Les services d’expérience client sont plus efficaces lorsqu’ils couvrent tout le séjour : communication avant l’arrivée, timing du check-in, readiness housekeeping, support sur place et suivi après le départ.</p>
                  <p>La même approche aide pour les demandes spéciales - recommandations de restaurants, livraison, départ tardif, chauffeur privé ou question locale. Au lieu de disparaître dans une boîte mail, la demande reste visible, assignable et facile à clôturer.</p>
                  <ul>
                    <li>Coordination des arrivées pour un check-in et des transferts sans friction.</li>
                    <li>Coordination housekeeping pour que le bien soit prêt au bon moment.</li>
                    <li>Support conciergerie pour les recommandations, réservations et l’aide locale.</li>
                    <li>Workflow de demandes qui garde chaque requête visible jusqu’à la fin.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="guest-experience-ops-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Conception opérationnelle</p>
                    <h2 id="guest-experience-ops-fr">Les opérations doivent rester discrètes pour que le client n’ait pas à y penser.</h2>
                  </div>
                  <p>Quand les opérations sont fragmentées, le client le remarque. Quand elles sont connectées, il se sent simplement accompagné. BlackSea Connect est construit autour de cette logique : mises à jour claires, responsabilité claire et suivi clair.</p>
                  <p>Ce fonctionnement laisse plus de temps à l’équipe pour la dimension humaine de l’hospitalité - le ton, le rythme et l’attention. Pour un modèle guest-facing sur des biens côtiers, la meilleure technologie est celle qui disparaît dans l’expérience tout en rendant l’équipe plus efficace.</p>
                </section>

                <section class="trust-layer" aria-labelledby="guest-experience-faq-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Questions fréquentes</p>
                    <h2 id="guest-experience-faq-fr">Questions des équipes hôtelières qui améliorent le parcours client.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>L’expérience client, c’est seulement la communication ?</h3>
                      <p>Non. La communication compte, mais la qualité du séjour dépend surtout du timing, de la coordination et du bon suivi.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Le workflow peut-il couvrir plusieurs types de biens ?</h3>
                      <p>Oui. Le même workflow fonctionne pour des villas, appartements et boutiques-hôtels avec des rythmes différents.</p>
                    </article>
                    <article class="trust-card">
                      <h3>La plateforme aide-t-elle avec les demandes récurrentes ?</h3>
                      <p>Oui. Les demandes répétées deviennent plus faciles à repérer, à router et à résoudre.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/concierge-bulgaria", "label": "Conciergerie en Bulgarie", "description": "Découvrez le workflow conciergerie qui soutient l’assistance client et la coordination locale."},
                {"href": "/property-management-bulgaria", "label": "Gestion immobilière en Bulgarie", "description": "Reliez le parcours client au modèle opérationnel du portefeuille côtier."},
                {"href": "/guest/a-302", "label": "Exemple de guest portal", "description": "Prévisualisez une expérience client pensée pour les arrivées et l’assistance."},
                {"href": "/services", "label": "Aperçu des services", "description": "Consultez la plateforme BlackSea Connect dans son ensemble."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Services d’expérience client",
                "url": "https://blackseaconnect.com/guest-experience-services",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "littoral de la mer Noire",
                "serviceType": [
                    "services d’expérience client",
                    "coordination des arrivées",
                    "guest concierge",
                    "workflow de demandes de service",
                ],
                "description": "Services d’expérience client pour les équipes hôtelières qui veulent des arrivées plus fluides, une communication plus claire, des séjours plus simples et un workflow pratique de demandes de service.",
            },
        },
        "ru": {
            "title": "BlackSea Connect | Сервисы guest experience",
            "description": "Сервисы guest experience для гостиничных команд, которым нужны более плавные прибытия, более ясная коммуникация, более спокойное проживание и практичный workflow заявок на услуги.",
            "h1": "Сервисы guest experience, которые делают пребывание лёгким",
            "eyebrow": "SEO-страница",
            "intro": "Guest experience часто описывают как ощущение, но за этим ощущением стоят конкретные операционные решения. Понятно ли прибытие? Успел ли housekeeping вовремя? Знает ли гость, к кому обратиться, если что-то меняется?",
            "keywords": ["сервисы guest experience", "координация прибытия гостей", "платформа hospitality operations", "guest concierge", "workflow заявок"],
            "ctas": [
                {"label": "Посмотреть примеры guest portal", "href": "/guest/a-302", "class": "button--primary"},
                {"label": "Открыть услуги", "href": "/services", "class": "button--secondary"},
                {"label": "Запросить поддержку", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="guest-experience-journey-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Путь гостя</p>
                    <h2 id="guest-experience-journey-ru">Guest experience начинается до прибытия и продолжается после выезда.</h2>
                  </div>
                  <p>Хорошая гостиничная операция не начинается у входа. Она начинается в момент бронирования, первого вопроса, запроса на трансфер или открытия guest portal. В этот момент команда уже должна знать объект, время, языковые предпочтения и вероятные потребности.</p>
                  <p>Когда этот контекст есть в операционной записи, гостю не нужно повторять одно и то же на каждом шаге. Пребывание становится проще, а команда работает спокойнее.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="guest-experience-touchpoints-ru">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Ключевые точки</p>
                    <h2 id="guest-experience-touchpoints-ru">Моменты, которые формируют запоминающееся пребывание.</h2>
                  </div>
                  <p>Сервисы guest experience работают лучше всего, когда покрывают весь путь гостя: до прибытия, во время check-in, при готовности housekeeping, при поддержке на месте и после выезда.</p>
                  <p>Тот же подход помогает и со специальными запросами - рекомендации, доставка, поздний выезд, частный водитель или локальный вопрос. Вместо того чтобы теряться в общей почте, запрос виден, назначаем и закрывается вовремя.</p>
                  <ul>
                    <li>Координация прибытия для спокойного check-in и трансферов.</li>
                    <li>Housekeeping-координация, чтобы объект был готов вовремя.</li>
                    <li>Guest concierge для рекомендаций, бронирований и локальной помощи.</li>
                    <li>Workflow заявок, который держит каждый запрос видимым до завершения.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="guest-experience-ops-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Операционный дизайн</p>
                    <h2 id="guest-experience-ops-ru">Операции должны оставаться незаметными, чтобы гость не думал о них.</h2>
                  </div>
                  <p>Когда процессы фрагментированы, гость это замечает. Когда они связаны, он просто чувствует поддержку. BlackSea Connect построен вокруг этого принципа: понятные обновления, понятная ответственность и понятный follow-through.</p>
                  <p>Это даёт команде больше времени на человеческую сторону гостеприимства - тон, ритм и внимание. Для guest-facing модели прибрежных объектов лучшая технология - та, которая исчезает в опыте, но делает команду сильнее.</p>
                </section>

                <section class="trust-layer" aria-labelledby="guest-experience-faq-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Частые вопросы</p>
                    <h2 id="guest-experience-faq-ru">Вопросы команд, которые улучшают путь гостя.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Guest experience - это только коммуникация?</h3>
                      <p>Нет. Коммуникация важна, но качество проживания чаще всего определяется таймингом, координацией и правильным follow-through.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Workflow может работать с разными типами объектов?</h3>
                      <p>Да. Один и тот же workflow подходит для вилл, апартаментов и boutique-объектов с разным ритмом работы.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Платформа помогает с повторяющимися запросами?</h3>
                      <p>Да. Повторяющиеся запросы легче заметить, направить и решить.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/concierge-bulgaria", "label": "Консьерж-услуги в Болгарии", "description": "Посмотрите консьерж workflow, который поддерживает помощь гостям и локальную координацию."},
                {"href": "/property-management-bulgaria", "label": "Управление недвижимостью в Болгарии", "description": "Свяжите путь гостя с более широким операционным моделью портфеля."},
                {"href": "/guest/a-302", "label": "Пример guest portal", "description": "Посмотрите guest-facing опыт, созданный для прибытия и поддержки."},
                {"href": "/services", "label": "Обзор услуг", "description": "Изучите платформу BlackSea Connect целиком."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Сервисы guest experience",
                "url": "https://blackseaconnect.com/guest-experience-services",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "побережье Чёрного моря",
                "serviceType": [
                    "сервисы guest experience",
                    "координация прибытия гостей",
                    "guest concierge",
                    "workflow заявок на услуги",
                ],
                "description": "Сервисы guest experience для гостиничных команд, которым нужны более плавные прибытия, более ясная коммуникация, более спокойное проживание и практичный workflow заявок на услуги.",
            },
        },
    },
    "/vacation-rental-operations": {
        "bg": {
            "title": "BlackSea Connect | Операции за ваканционни наеми",
            "description": "Операции за ваканционни наеми за крайбрежни портфейли, които имат нужда от housekeeping координация, guest arrival координация, управление на трансфери и доверени местни партньори в мащаб.",
            "h1": "Операции за ваканционни наеми, създадени за крайбрежен мащаб",
            "eyebrow": "SEO landing page",
            "intro": "Операциите при ваканционни наеми лесно се подценяват, докато портфейлът не започне да расте. Това, което е било няколко имота, бързо се превръща във верига от turnovers, пристигания, проверки на housekeeping, въпроси за трансфери и отчети към собственици.",
            "keywords": ["операции за ваканционни наеми", "housekeeping координация", "guest arrival координация", "операции за крайбрежни имоти", "доверени местни партньори"],
            "ctas": [
                {"label": "Вижте демо потока", "href": "/demo/operations", "class": "button--primary"},
                {"label": "Разгледайте партньорите", "href": "/network", "class": "button--secondary"},
                {"label": "Заявете услуга", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="vacation-rental-scale-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Мащаб без загуба на контрол</p>
                    <h2 id="vacation-rental-scale-bg">Растящият портфейл има нужда от повторяем операционен систем.</h2>
                  </div>
                  <p>С разрастването на ваканционните наеми рисковете се променят. Една пропусната смяна може да повлияе на следващи пристигания. Един забавен трансфер може да обърка housekeeping графика. BlackSea Connect пази тези движещи се части видими, за да се защити качеството на услугата.</p>
                  <p>Платформата не скрива работата, а я подрежда. Екипът вижда кой е отговорен, какво следва и кога задачата е приключена. Това помага на мениджърите да преминат от реактивно решаване към по-предвидим стандарт на грижа.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="vacation-rental-core-bg">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Основни потоци</p>
                    <h2 id="vacation-rental-core-bg">Housekeeping, пристиганията и заявките са сърцето на портфейла.</h2>
                  </div>
                  <p>Ваканционните наеми успяват или се провалят в детайла. Чистото предаване е обещание към следващия гост. Навременният трансфер задава тон за целия престой. BlackSea Connect държи тези базови процеси подредени в една система.</p>
                  <p>Същият workflow помага и с доверените местни партньори. Когато поддръжка, шофьори, почистващи екипи и concierge контакти са координирани, екипът работи по-бързо и с по-малко шум.</p>
                  <ul>
                    <li>Координация на checkout, turnover и same-day arrivals.</li>
                    <li>Housekeeping координация между обекти, сгради и различни сезонни графици.</li>
                    <li>Диспетчеризация на доверени местни партньори за трансфери и спешна поддръжка.</li>
                    <li>Един workflow за заявки за гости, собственици и вътрешни екипи.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="vacation-rental-owners-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Увереност на собственика</p>
                    <h2 id="vacation-rental-owners-bg">Собствениците искат видимост, не само активност.</h2>
                  </div>
                  <p>Едно от най-големите предизвикателства е превръщането на ежедневната работа в нещо, което собственикът разбира. BlackSea Connect подрежда основната работа така, че комуникацията със собственика да бъде по-ясна, по-точна и по-надеждна.</p>
                  <p>Когато екипът вижда кои заявки се повтарят, кои имоти изискват повече внимание и кои партньори са най-надеждни, управлението може да подобри staffing-а и да вземе по-добри решения за портфейла.</p>
                </section>

                <section class="trust-layer" aria-labelledby="vacation-rental-faq-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Често задавани въпроси</p>
                    <h2 id="vacation-rental-faq-bg">Въпроси от оператори, които мащабират ваканционни наеми по Черноморието.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Само за големи портфейли ли е?</h3>
                      <p>Не. Същият workflow помага и на един оператор, и на растящ портфейл, защото проблемът е координацията.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Помага ли при same-day turnovers?</h3>
                      <p>Да. Same-day turnover е един от най-силните случаи за структурирана housekeeping координация.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Може ли да намали забавянията пред госта?</h3>
                      <p>Да. По-ясната координация на пристиганията и по-добрият dispatch намаляват малките забавяния, които дразнят госта най-много.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/property-management-bulgaria", "label": "Управление на имоти в България", "description": "Научете как да държите крайбрежния портфейл организиран и видим."},
                {"href": "/guest-experience-services", "label": "Услуги за гостско преживяване", "description": "Вижте как пътят на госта се свързва с back-office workflow-а."},
                {"href": "/network", "label": "Мрежа от доставчици", "description": "Намерете одобрени местни партньори, които да поддържат операцията."},
                {"href": "/demo/operations", "label": "Оперативно демо", "description": "Вижте работния поток на платформата в спокоен и практичен интерфейс."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Операции за ваканционни наеми",
                "url": "https://blackseaconnect.com/vacation-rental-operations",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Черноморският бряг",
                "serviceType": [
                    "операции за ваканционни наеми",
                    "housekeeping координация",
                    "guest arrival координация",
                    "доверени местни партньори",
                ],
                "description": "Операции за ваканционни наеми за крайбрежни портфейли, които имат нужда от housekeeping координация, guest arrival координация, управление на трансфери и доверени местни партньори в мащаб.",
            },
        },
        "fr": {
            "title": "BlackSea Connect | Opérations de locations saisonnières",
            "description": "Opérations de locations saisonnières pour portefeuilles côtiers qui ont besoin de coordination housekeeping, de coordination des arrivées, de gestion des transferts et de partenaires locaux de confiance à grande échelle.",
            "h1": "Des opérations de locations saisonnières pensées pour l’échelle côtière",
            "eyebrow": "Page SEO",
            "intro": "Les opérations de locations saisonnières sont faciles à sous-estimer jusqu’au jour où le portefeuille commence à grandir. Quelques biens deviennent vite une chaîne de turnovers, d’arrivées, de contrôles housekeeping, de questions de transfert et de retours propriétaires.",
            "keywords": ["opérations locations saisonnières", "coordination housekeeping", "coordination des arrivées", "opérations de biens côtiers", "partenaires locaux de confiance"],
            "ctas": [
                {"label": "Voir la démo", "href": "/demo/operations", "class": "button--primary"},
                {"label": "Parcourir le réseau", "href": "/network", "class": "button--secondary"},
                {"label": "Demander un service", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="vacation-rental-scale-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Grandir sans perdre le contrôle</p>
                    <h2 id="vacation-rental-scale-fr">Un portefeuille en croissance a besoin d’un système répétable.</h2>
                  </div>
                  <p>À mesure que les locations saisonnières se développent, les risques changent. Un turnover manqué peut impacter la suite des arrivées. Un transfert retardé peut décaler le housekeeping. BlackSea Connect garde ces éléments visibles pour protéger la qualité de service.</p>
                  <p>La plateforme ne cache pas le travail, elle l’organise. L’équipe voit qui est responsable, quelle est la prochaine étape et quand la tâche est terminée. Cela aide les managers à passer d’une logique réactive à un standard de soin plus prévisible.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="vacation-rental-core-fr">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Flux essentiels</p>
                    <h2 id="vacation-rental-core-fr">Housekeeping, arrivées et demandes sont le cœur du portefeuille.</h2>
                  </div>
                  <p>Une location saisonnière réussit ou échoue souvent dans les détails. Un turnover propre est une promesse faite au prochain client. Un transfert à l’heure donne le ton du séjour. BlackSea Connect organise ces bases dans un workflow clair.</p>
                  <p>Le même système aide aussi avec les partenaires locaux de confiance. Quand l’entretien, les chauffeurs, les équipes de nettoyage et la conciergerie sont coordonnés, l’équipe avance plus vite et avec moins de bruit.</p>
                  <ul>
                    <li>Coordination des check-out, turnovers et arrivées le jour même.</li>
                    <li>Coordination housekeeping entre biens, bâtiments et saisons différentes.</li>
                    <li>Dispatch des partenaires locaux pour transferts et maintenance urgente.</li>
                    <li>Un seul workflow pour les demandes des clients, des propriétaires et de l’interne.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="vacation-rental-owners-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Confiance propriétaire</p>
                    <h2 id="vacation-rental-owners-fr">Les propriétaires veulent de la visibilité, pas seulement de l’activité.</h2>
                  </div>
                  <p>L’un des grands défis consiste à transformer le travail quotidien en quelque chose de compréhensible pour le propriétaire. BlackSea Connect organise ce travail pour rendre les échanges plus clairs, plus précis et plus fiables.</p>
                  <p>Quand l’équipe voit les demandes récurrentes, les biens qui demandent plus d’attention et les partenaires les plus fiables, la gestion peut améliorer le staffing et faire de meilleurs choix pour le portefeuille.</p>
                </section>

                <section class="trust-layer" aria-labelledby="vacation-rental-faq-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Questions fréquentes</p>
                    <h2 id="vacation-rental-faq-fr">Questions des opérateurs qui développent des locations côtières.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Est-ce réservé aux grands portefeuilles ?</h3>
                      <p>Non. Le même workflow aide un opérateur unique comme un portefeuille en croissance, car le vrai problème est la coordination.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Aide-t-il pour les turnovers le jour même ?</h3>
                      <p>Oui. Le turnover le jour même est un cas idéal pour une coordination housekeeping structurée.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Peut-il réduire les retards côté client ?</h3>
                      <p>Oui. Une coordination d’arrivées plus claire et un meilleur dispatch réduisent les petits retards qui frustrent le plus les clients.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/property-management-bulgaria", "label": "Gestion immobilière en Bulgarie", "description": "Apprenez à garder un portefeuille côtier organisé et visible."},
                {"href": "/guest-experience-services", "label": "Services d’expérience client", "description": "Voyez comment le parcours client se connecte au workflow back-office."},
                {"href": "/network", "label": "Réseau de prestataires", "description": "Trouvez des partenaires locaux approuvés pour soutenir l’opération."},
                {"href": "/demo/operations", "label": "Démo opérationnelle", "description": "Découvrez le workflow de la plateforme dans une interface calme et pratique."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Opérations de locations saisonnières",
                "url": "https://blackseaconnect.com/vacation-rental-operations",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "littoral de la mer Noire",
                "serviceType": [
                    "opérations de locations saisonnières",
                    "coordination housekeeping",
                    "coordination des arrivées",
                    "partenaires locaux de confiance",
                ],
                "description": "Opérations de locations saisonnières pour portefeuilles côtiers qui ont besoin de coordination housekeeping, de coordination des arrivées, de gestion des transferts et de partenaires locaux de confiance à grande échelle.",
            },
        },
        "ru": {
            "title": "BlackSea Connect | Операции vacation rental",
            "description": "Операции vacation rental для прибрежных портфелей, которым нужны координация housekeeping, координация прибытия гостей, управление трансферами и проверенные местные партнёры в масштабе.",
            "h1": "Операции vacation rental, созданные для прибрежного масштаба",
            "eyebrow": "SEO-страница",
            "intro": "Операции vacation rental легко недооценить, пока портфель не начнёт расти. Несколько объектов быстро превращаются в цепочку turnovers, прибытия гостей, проверок housekeeping, вопросов по трансферам и отчётов владельцам.",
            "keywords": ["операции vacation rental", "координация housekeeping", "координация прибытия гостей", "операции прибрежной недвижимости", "проверенные местные партнёры"],
            "ctas": [
                {"label": "Посмотреть demo-поток", "href": "/demo/operations", "class": "button--primary"},
                {"label": "Открыть сеть", "href": "/network", "class": "button--secondary"},
                {"label": "Запросить услугу", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="vacation-rental-scale-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Рост без потери контроля</p>
                    <h2 id="vacation-rental-scale-ru">Растущему портфелю нужна повторяемая система.</h2>
                  </div>
                  <p>По мере роста vacation rental риски меняются. Пропущенный turnover влияет на следующие прибытия. Задержанный трансфер сдвигает housekeeping. BlackSea Connect делает эти элементы видимыми, чтобы защищать качество сервиса.</p>
                  <p>Платформа не прячет работу, а упорядочивает её. Команда видит, кто отвечает, что дальше и когда задача закрыта. Это помогает менеджерам перейти от реактивных решений к более предсказуемому стандарту ухода.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="vacation-rental-core-ru">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Основные потоки</p>
                    <h2 id="vacation-rental-core-ru">Housekeeping, прибытия и заявки - сердце портфеля.</h2>
                  </div>
                  <p>Vacation rental часто выигрывает или проигрывает в деталях. Чистый turnover - это обещание следующему гостю. Прибытие вовремя задаёт тон всему проживанию. BlackSea Connect организует эти базовые процессы в понятный workflow.</p>
                  <p>Та же система помогает с проверенными местными партнёрами. Когда обслуживание, водители, клининговые команды и concierge связаны, команда работает быстрее и спокойнее.</p>
                  <ul>
                    <li>Координация check-out, turnovers и same-day arrivals.</li>
                    <li>Housekeeping-координация между объектами, зданиями и сезонными графиками.</li>
                    <li>Dispatch местных партнёров для трансферов и срочного обслуживания.</li>
                    <li>Один workflow для запросов гостей, владельцев и внутренней команды.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="vacation-rental-owners-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Уверенность владельца</p>
                    <h2 id="vacation-rental-owners-ru">Владельцам нужна видимость, а не просто активность.</h2>
                  </div>
                  <p>Одна из главных задач - превратить ежедневную работу в то, что понятно владельцу. BlackSea Connect упорядочивает работу так, чтобы коммуникация с владельцем была яснее, точнее и надёжнее.</p>
                  <p>Когда команда видит повторяющиеся заявки, объекты, требующие большего внимания, и самых надёжных партнёров, управление может улучшить staffing и принимать лучшие решения по портфелю.</p>
                </section>

                <section class="trust-layer" aria-labelledby="vacation-rental-faq-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Частые вопросы</p>
                    <h2 id="vacation-rental-faq-ru">Вопросы операторов, которые масштабируют прибрежные vacation rentals.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Это только для больших портфелей?</h3>
                      <p>Нет. Один и тот же workflow помогает и одному оператору, и растущему портфелю, потому что проблема - это координация.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Помогает ли при same-day turnovers?</h3>
                      <p>Да. Same-day turnover - отличный сценарий для структурированной housekeeping-координации.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Может ли уменьшить задержки для гостя?</h3>
                      <p>Да. Более ясная координация прибытия и лучший dispatch уменьшают небольшие задержки, которые больше всего раздражают гостей.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/property-management-bulgaria", "label": "Управление недвижимостью в Болгарии", "description": "Узнайте, как держать прибрежный портфель организованным и видимым."},
                {"href": "/guest-experience-services", "label": "Сервисы guest experience", "description": "Посмотрите, как путь гостя связан с back-office workflow."},
                {"href": "/network", "label": "Сеть партнёров", "description": "Найдите проверенных местных партнёров для поддержки операции."},
                {"href": "/demo/operations", "label": "Операционное демо", "description": "Посмотрите workflow платформы в спокойном и практичном интерфейсе."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Операции vacation rental",
                "url": "https://blackseaconnect.com/vacation-rental-operations",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "побережье Чёрного моря",
                "serviceType": [
                    "операции vacation rental",
                    "координация housekeeping",
                    "координация прибытия гостей",
                    "проверенные местные партнёры",
                ],
                "description": "Операции vacation rental для прибрежных портфелей, которым нужны координация housekeeping, координация прибытия гостей, управление трансферами и проверенные местные партнёры в масштабе.",
            },
        },
    },
    "/property-management-bulgaria": {
        "bg": {
            "title": "BlackSea Connect | Управление на имоти в България",
            "description": "Управление на имоти в България за крайбрежни оператори, които имат нужда от housekeeping координация, guest arrival координация, проследяване на поддръжка и доверени местни партньори в една платформа.",
            "h1": "Управление на имоти в България за крайбрежни портфейли",
            "eyebrow": "SEO landing page",
            "intro": "Управлението на имоти в България е различно, когато активите са крайбрежни. Смените са по-стегнати, пристиганията са по-чувствителни към време, поддръжката е сезонна, а очакванията на собствениците се променят бързо със заетостта.",
            "keywords": ["управление на имоти България", "операции за крайбрежни имоти", "housekeeping координация", "guest arrival координация", "доверени местни партньори"],
            "ctas": [
                {"label": "Разгледайте operations", "href": "/services", "class": "button--primary"},
                {"label": "Вижте директорията с партньори", "href": "/network", "class": "button--secondary"},
                {"label": "Заявете workflow", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="pm-bulgaria-context-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Реалността на крайбрежното управление</p>
                    <h2 id="pm-bulgaria-context-bg">Управлението на имоти в България има нужда от повече от checklist.</h2>
                  </div>
                  <p>Крайбрежните портфейли се формират от сезонност, пътувания и темпото на turnover. Мениджърът координира housekeeping, check-in прозорци, maintenance посещения и отчети към собствениците в рамките на един ден.</p>
                  <p>BlackSea Connect дава система за тази работа: място за заявката, място за assign и място за статуса, без да се гонят обновления из различни канали.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="pm-bulgaria-scope-bg">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Оперативен обхват</p>
                    <h2 id="pm-bulgaria-scope-bg">Основната работа на крайбрежния property manager.</h2>
                  </div>
                  <p>Property management е поредица от малки решения: кой обект се инспектира, кое пристигане трябва да се актуализира, коя поддръжка трябва да се свърши преди следващия гост. BlackSea Connect държи тези решения видими.</p>
                  <p>Платформата помага и с доверените местни партньори. Когато правилният човек е известен за конкретна задача, екипът работи по-бързо, без да губи отговорност.</p>
                  <ul>
                    <li>Координация на check-in, turnover и inspection timing за повече имоти.</li>
                    <li>Проследяване на поддръжка, housekeeping и guest service заявки в един workflow.</li>
                    <li>Управление на доверени местни партньори без загуба на контекст.</li>
                    <li>По-спокоен оперативен преглед и по-последователни стандарти за собствениците.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="pm-bulgaria-portfolio-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Контрол върху портфейла</p>
                    <h2 id="pm-bulgaria-portfolio-bg">По-добър начин да управлявате вили, апартаменти и смесени портфейли.</h2>
                  </div>
                  <p>Собствениците искат увереност, че работата е планирана, разпределена и завършена. Това е особено важно, когато портфейлът включва различни типове сгради или няколко крайбрежни града.</p>
                  <p>Платформата подпомага и преминаването от реактивно към проактивно управление. Когато екипът вижда модели в заявките, housekeeping тайминга и transfer delays, той взима по-добри решения за staffing и партньорите.</p>
                </section>

                <section class="trust-layer" aria-labelledby="pm-bulgaria-faq-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Често задавани въпроси</p>
                    <h2 id="pm-bulgaria-faq-bg">Въпроси от крайбрежни оператори за управлението на имоти.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Замества ли това property manager-а?</h3>
                      <p>Не. Подпомага го, като държи координацията, guest requests и partner work видими в цялата операция.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Работи ли за вили и апартаменти заедно?</h3>
                      <p>Да. Платформата е направена за смесени крайбрежни портфейли с общ оперативен модел.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Полезна ли е извън сезона?</h3>
                      <p>Много. Тихите месеци са идеални за подобряване на workflow-ите и подготовка за следващия сезон.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/vacation-rental-operations", "label": "Операции за ваканционни наеми", "description": "Вижте модела за многoобектни портфейли, turnovers и повторяеми стандарти."},
                {"href": "/concierge-bulgaria", "label": "Консиерж услуги в България", "description": "Разберете как гостската подкрепа и партньорите се вписват в операцията."},
                {"href": "/guest-experience-services", "label": "Услуги за гостско преживяване", "description": "Разгледайте guest-facing страната на същата платформа."},
                {"href": "/network", "label": "Одобрена мрежа от доставчици", "description": "Прегледайте доверената директория, която захранва workflow-а."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Управление на имоти в България",
                "url": "https://blackseaconnect.com/property-management-bulgaria",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "България",
                "serviceType": [
                    "управление на имоти",
                    "housekeeping координация",
                    "guest arrival координация",
                    "доверени местни партньори",
                ],
                "description": "Управление на имоти в България за крайбрежни оператори, които имат нужда от housekeeping координация, guest arrival координация, проследяване на поддръжка и доверени местни партньори в една платформа.",
            },
        },
        "fr": {
            "title": "BlackSea Connect | Gestion immobilière en Bulgarie",
            "description": "Gestion immobilière en Bulgarie pour les opérateurs côtiers qui ont besoin de coordination housekeeping, de coordination des arrivées, de suivi de maintenance et de partenaires locaux de confiance dans une seule plateforme.",
            "h1": "Gestion immobilière en Bulgarie pour les portefeuilles côtiers",
            "eyebrow": "Page SEO",
            "intro": "La gestion immobilière en Bulgarie change lorsque les actifs sont côtiers. Les turnovers sont plus serrés, les arrivées sont plus sensibles au timing, la maintenance est saisonnière et les attentes des propriétaires évoluent vite avec l’occupation.",
            "keywords": ["gestion immobilière Bulgarie", "opérations de biens côtiers", "coordination housekeeping", "coordination des arrivées", "partenaires locaux de confiance"],
            "ctas": [
                {"label": "Découvrir les opérations", "href": "/services", "class": "button--primary"},
                {"label": "Voir le réseau", "href": "/network", "class": "button--secondary"},
                {"label": "Demander un workflow", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="pm-bulgaria-context-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">La réalité de la côte</p>
                    <h2 id="pm-bulgaria-context-fr">La gestion immobilière en Bulgarie a besoin de plus qu’une checklist.</h2>
                  </div>
                  <p>Les portefeuilles côtiers sont façonnés par la saison, les déplacements et le rythme des turnovers. Le manager coordonne housekeeping, fenêtres de check-in, visites de maintenance et reporting propriétaire dans la même journée.</p>
                  <p>BlackSea Connect fournit un système pour ce travail : un endroit pour la demande, un endroit pour l’assignation et un endroit pour le statut, sans courir après les mises à jour dans plusieurs canaux.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="pm-bulgaria-scope-fr">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Champ opérationnel</p>
                    <h2 id="pm-bulgaria-scope-fr">Le travail principal du property manager côtier.</h2>
                  </div>
                  <p>La gestion immobilière est une suite de petites décisions : quel bien inspecter, quelle arrivée doit être mise à jour, quelle maintenance doit être faite avant le prochain client. BlackSea Connect garde ces décisions visibles.</p>
                  <p>La plateforme aide aussi avec les partenaires locaux de confiance. Quand la bonne personne est connue pour une tâche précise, l’équipe agit plus vite sans perdre la responsabilité.</p>
                  <ul>
                    <li>Coordination du check-in, du turnover et du timing d’inspection sur plusieurs biens.</li>
                    <li>Suivi de la maintenance, du housekeeping et des demandes clients dans un workflow.</li>
                    <li>Gestion des partenaires locaux de confiance sans perdre de contexte.</li>
                    <li>Vue opérationnelle plus calme et standards plus cohérents pour les propriétaires.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="pm-bulgaria-portfolio-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Contrôle du portefeuille</p>
                    <h2 id="pm-bulgaria-portfolio-fr">Une meilleure façon de gérer villas, appartements et portefeuilles mixtes.</h2>
                  </div>
                  <p>Les propriétaires veulent la confiance que le travail est planifié, réparti et terminé. C’est particulièrement important lorsque le portefeuille couvre plusieurs types de bâtiments ou plusieurs villes côtières.</p>
                  <p>La plateforme aide aussi à passer d’une gestion réactive à une gestion proactive. Quand l’équipe voit les tendances dans les demandes, le timing housekeeping et les retards de transfert, elle prend de meilleures décisions de staffing et de partenaires.</p>
                </section>

                <section class="trust-layer" aria-labelledby="pm-bulgaria-faq-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Questions fréquentes</p>
                    <h2 id="pm-bulgaria-faq-fr">Questions des opérateurs côtiers sur la gestion immobilière.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Est-ce que cela remplace le property manager ?</h3>
                      <p>Non. Cela l’aide en gardant la coordination, les demandes clients et le travail des partenaires visibles.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Est-ce que ça marche pour villas et appartements ensemble ?</h3>
                      <p>Oui. La plateforme est pensée pour des portefeuilles côtiers mixtes avec un modèle opérationnel commun.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Est-ce utile hors saison ?</h3>
                      <p>Oui. Les mois calmes sont parfaits pour améliorer les workflows et préparer la haute saison.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/vacation-rental-operations", "label": "Opérations de locations saisonnières", "description": "Voir le modèle pour les portefeuilles multi-biens et les turnovers répétables."},
                {"href": "/concierge-bulgaria", "label": "Conciergerie en Bulgarie", "description": "Comprendre comment l’assistance client et les partenaires s’intègrent à l’opération."},
                {"href": "/guest-experience-services", "label": "Services d’expérience client", "description": "Explorer le côté client de la même plateforme côtière."},
                {"href": "/network", "label": "Réseau approuvé", "description": "Parcourir le répertoire de partenaires de confiance qui alimente le workflow."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Gestion immobilière en Bulgarie",
                "url": "https://blackseaconnect.com/property-management-bulgaria",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Bulgarie",
                "serviceType": [
                    "gestion immobilière",
                    "coordination housekeeping",
                    "coordination des arrivées",
                    "partenaires locaux de confiance",
                ],
                "description": "Gestion immobilière en Bulgarie pour les opérateurs côtiers qui ont besoin de coordination housekeeping, de coordination des arrivées, de suivi de maintenance et de partenaires locaux de confiance dans une seule plateforme.",
            },
        },
        "ru": {
            "title": "BlackSea Connect | Управление недвижимостью в Болгарии",
            "description": "Управление недвижимостью в Болгарии для прибрежных операторов, которым нужна координация housekeeping, координация прибытия гостей, учёт обслуживания и проверенные местные партнёры в одной платформе.",
            "h1": "Управление недвижимостью в Болгарии для прибрежных портфелей",
            "eyebrow": "SEO-страница",
            "intro": "Управление недвижимостью в Болгарии меняется, когда активы находятся у моря. Смены плотнее, прибытия чувствительнее к времени, обслуживание сезонное, а ожидания владельцев быстро меняются вместе с загрузкой.",
            "keywords": ["управление недвижимостью Болгария", "операции прибрежной недвижимости", "координация housekeeping", "координация прибытия гостей", "проверенные местные партнёры"],
            "ctas": [
                {"label": "Изучить operations", "href": "/services", "class": "button--primary"},
                {"label": "Посмотреть сеть", "href": "/network", "class": "button--secondary"},
                {"label": "Запросить workflow", "href": "/request-service", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="pm-bulgaria-context-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Реальность прибрежного управления</p>
                    <h2 id="pm-bulgaria-context-ru">Управлению недвижимостью в Болгарии нужно больше, чем checklist.</h2>
                  </div>
                  <p>Прибрежные портфели определяются сезонностью, поездками и ритмом turnovers. Менеджер координирует housekeeping, окна check-in, maintenance-визиты и отчёты владельцам в один и тот же день.</p>
                  <p>BlackSea Connect даёт систему для этой работы: место для запроса, место для назначения и место для статуса, без постоянной гонки за обновлениями.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="pm-bulgaria-scope-ru">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Операционный охват</p>
                    <h2 id="pm-bulgaria-scope-ru">Основная работа прибрежного property manager-а.</h2>
                  </div>
                  <p>Управление недвижимостью - это цепочка маленьких решений: какой объект инспектировать, какое прибытие обновить, какое обслуживание сделать до следующего гостя. BlackSea Connect держит эти решения видимыми.</p>
                  <p>Платформа помогает и с проверенными местными партнёрами. Когда нужный человек известен для конкретной задачи, команда работает быстрее, не теряя ответственности.</p>
                  <ul>
                    <li>Координация check-in, turnover и inspection timing для нескольких объектов.</li>
                    <li>Учёт maintenance, housekeeping и guest service запросов в одном workflow.</li>
                    <li>Управление проверенными местными партнёрами без потери контекста.</li>
                    <li>Более спокойная операционная картина и более стабильные стандарты для владельцев.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="pm-bulgaria-portfolio-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Контроль портфеля</p>
                    <h2 id="pm-bulgaria-portfolio-ru">Лучший способ управлять виллами, квартирами и смешанными портфелями.</h2>
                  </div>
                  <p>Владельцы хотят уверенности, что работа спланирована, распределена и завершена. Это особенно важно, когда портфель охватывает разные типы зданий или несколько прибрежных городов.</p>
                  <p>Платформа помогает перейти от реактивного к проактивному управлению. Когда команда видит тенденции в запросах, housekeeping-тайминге и transfer delays, она принимает лучшие решения по staffing и партнёрам.</p>
                </section>

                <section class="trust-layer" aria-labelledby="pm-bulgaria-faq-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Частые вопросы</p>
                    <h2 id="pm-bulgaria-faq-ru">Вопросы прибрежных операторов об управлении недвижимостью.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Это заменяет property manager-а?</h3>
                      <p>Нет. Это помогает ему, делая координацию, запросы гостей и работу партнёров видимыми во всей операции.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Подходит ли для вилл и апартаментов вместе?</h3>
                      <p>Да. Платформа создана для смешанных прибрежных портфелей с общим операционным моделем.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Полезна ли она вне сезона?</h3>
                      <p>Очень. Спокойные месяцы идеальны для улучшения workflow и подготовки к следующему сезону.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/vacation-rental-operations", "label": "Операции vacation rental", "description": "Посмотрите модель для многoобъектных портфелей и повторяемых turnovers."},
                {"href": "/concierge-bulgaria", "label": "Консьерж-услуги в Болгарии", "description": "Поймите, как guest support и партнёры вписываются в операцию."},
                {"href": "/guest-experience-services", "label": "Сервисы guest experience", "description": "Изучите клиентскую сторону той же прибрежной платформы."},
                {"href": "/network", "label": "Одобренная сеть", "description": "Просмотрите каталог проверенных партнёров, который питает workflow."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Управление недвижимостью в Болгарии",
                "url": "https://blackseaconnect.com/property-management-bulgaria",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Болгария",
                "serviceType": [
                    "управление недвижимостью",
                    "координация housekeeping",
                    "координация прибытия гостей",
                    "проверенные местные партнёры",
                ],
                "description": "Управление недвижимостью в Болгарии для прибрежных операторов, которым нужна координация housekeeping, координация прибытия гостей, учёт обслуживания и проверенные местные партнёры в одной платформе.",
            },
        },
    },
    "/sveti-vlas-concierge-services": {
        "bg": {
            "title": "BlackSea Connect | Консиерж услуги в Свети Влас",
            "description": "Консиерж услуги в Свети Влас за крайбрежни имоти близо до марината, апартаменти на първа линия и вили по хълма, които имат нужда от надеждна гостоприемна подкрепа и локална координация.",
            "h1": "Консиерж услуги в Свети Влас за крайбрежни имоти и марина престои",
            "eyebrow": "SEO landing page",
            "intro": "Консиерж услугите в Свети Влас трябва да отразяват местния ритъм: движение в марината, крайбрежни маршрути и комплекси, които приемат семейства, яхтени пътешественици и редовни гости.",
            "keywords": ["консиерж услуги Свети Влас", "гост-сървиз", "управление на имоти Черно море", "guest arrival координация", "доверени местни партньори"],
            "ctas": [
                {"label": "Заявете подкрепа за Свети Влас", "href": "/request-service", "class": "button--primary"},
                {"label": "Разгледайте консиерж услугите", "href": "/concierge-bulgaria", "class": "button--secondary"},
                {"label": "Вижте партньорите", "href": "/network", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="sveti-vlas-local-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Локален контекст</p>
                    <h2 id="sveti-vlas-local-bg">Свети Влас е място, където консиерж работата следва много специфичен крайбрежен ритъм.</h2>
                  </div>
                  <p>Марина трафикът, плажното темпо, сезонността и очакванията на гостите, които пристигат с кола, трансфер или лодка, изискват локално разбиране. BlackSea Connect управлява тази сложност в една оперативна система.</p>
                  <p>Arrival координацията, housekeeping обновленията и партньорският dispatch се случват в един workflow, за да бъде престоят подреден и премиум.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="sveti-vlas-needs-bg">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Какво търсят гостите</p>
                    <h2 id="sveti-vlas-needs-bg">Най-честите заявки са оперативни, не декоративни.</h2>
                  </div>
                  <p>В крайбрежна локация малките детайли доминират. Забавен трансфер променя началото на престоя. Късен housekeeping finish влияе на check-in прозореца. Пропусната локална препоръка кара госта да се чувства откъснат от мястото.</p>
                  <p>BlackSea Connect държи тези моменти подредени чрез workflow за заявки, който насочва задачата към правилния човек и я пази видима до приключване.</p>
                  <ul>
                    <li>Координация на пристигания за марина пристигания, частни шофьори и късни check-in-и.</li>
                    <li>Housekeeping координация за плажни апартаменти, вили по хълма и смесени обекти.</li>
                    <li>Concierge support за хранене, транспорт, резервации и ориентация в дестинацията.</li>
                    <li>Доверени местни партньори, които могат да реагират, когато таймингът е критичен.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="sveti-vlas-ops-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Оперативно предимство</p>
                    <h2 id="sveti-vlas-ops-bg">Най-добрите консиерж услуги карат имота да изглежда подреден.</h2>
                  </div>
                  <p>Гостът рядко вижда координационния слой, но усеща резултата веднага. Когато пристигането е навреме, имотът е готов и локалната поддръжка реагира, престоят изглежда подреден.</p>
                  <p>Същата система работи и при различни типове имоти - марина апартамент, вилa на хълма или семейно жилище. Общият стандарт остава, но детайлите се адаптират към мястото.</p>
                </section>

                <section class="trust-layer" aria-labelledby="sveti-vlas-faq-bg">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Често задавани въпроси</p>
                    <h2 id="sveti-vlas-faq-bg">Въпроси от екипи и хостове в Свети Влас.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Може ли да поддържа имоти до марината?</h3>
                      <p>Да. Марина пристиганията изискват прецизен тайминг и надеждна координация на партньори.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Полезно ли е за вили и апартаменти по хълма?</h3>
                      <p>Да. Различните типове имоти могат да използват един и същ оперативен модел с различни бележки и нужди.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Помага ли при сезонно търсене?</h3>
                      <p>Да. Сезонното търсене се управлява по-лесно, когато заявките и партньорите са видими в един workflow.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/concierge-bulgaria", "label": "Консиерж услуги в България", "description": "Прочетете по-широката стратегия за консиерж услуги по Черноморието."},
                {"href": "/guest-experience-services", "label": "Услуги за гостско преживяване", "description": "Вижте как Свети Влас се вписва в по-широкия гостски път."},
                {"href": "/property-management-bulgaria", "label": "Управление на имоти в България", "description": "Свържете локалната операция с цялата портфейлна система."},
                {"href": "/request-service", "label": "Заявете подкрепа", "description": "Започнете заявка и я проведете през оперативния workflow."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Консиерж услуги в Свети Влас",
                "url": "https://blackseaconnect.com/sveti-vlas-concierge-services",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Свети Влас",
                "serviceType": [
                    "консиерж услуги",
                    "гост-сървиз",
                    "guest arrival координация",
                    "доверени местни партньори",
                ],
                "description": "Консиерж услуги в Свети Влас за крайбрежни имоти близо до марината, апартаменти на първа линия и вили по хълма, които имат нужда от надеждна гостоприемна подкрепа и локална координация.",
            },
        },
        "fr": {
            "title": "BlackSea Connect | Services de conciergerie à Sveti Vlas",
            "description": "Services de conciergerie à Sveti Vlas pour les biens côtiers près de la marina, les appartements en front de mer et les villas sur les hauteurs qui ont besoin d’un support fiable et d’une coordination locale.",
            "h1": "Services de conciergerie à Sveti Vlas pour biens côtiers et séjours marina",
            "eyebrow": "Page SEO",
            "intro": "Les services de conciergerie à Sveti Vlas doivent refléter le rythme local : circulation autour de la marina, routes côtières et ensembles résidentiels pour familles, voyageurs nautiques et visiteurs réguliers.",
            "keywords": ["services de conciergerie Sveti Vlas", "guest concierge", "gestion immobilière mer Noire", "coordination des arrivées", "partenaires locaux de confiance"],
            "ctas": [
                {"label": "Demander un support Sveti Vlas", "href": "/request-service", "class": "button--primary"},
                {"label": "Explorer la conciergerie", "href": "/concierge-bulgaria", "class": "button--secondary"},
                {"label": "Voir les partenaires", "href": "/network", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="sveti-vlas-local-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Contexte local</p>
                    <h2 id="sveti-vlas-local-fr">Sveti Vlas est un lieu où la conciergerie suit un rythme côtier très précis.</h2>
                  </div>
                  <p>Le trafic de marina, le rythme de la plage, la saisonnalité et les attentes des clients qui arrivent en voiture, en transfert ou en bateau demandent une vraie lecture locale. BlackSea Connect gère cette complexité dans un seul workflow.</p>
                  <p>La coordination des arrivées, les mises à jour housekeeping et le dispatch des partenaires se font dans un flux opérationnel unique pour garder le séjour fluide et premium.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="sveti-vlas-needs-fr">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Ce que veulent les clients</p>
                    <h2 id="sveti-vlas-needs-fr">Les demandes les plus fréquentes sont opérationnelles, pas décoratives.</h2>
                  </div>
                  <p>Dans une zone côtière, les détails pèsent lourd. Un transfert retardé modifie le début du séjour. Un housekeeping tardif affecte le check-in. Une recommandation locale manquée donne au client l’impression d’être coupé de la destination.</p>
                  <p>BlackSea Connect garde ces moments organisés via un workflow de demandes qui envoie la tâche à la bonne personne et la maintient visible jusqu’à la fin.</p>
                  <ul>
                    <li>Coordination des arrivées pour les arrivées marina, chauffeurs privés et check-in tardifs.</li>
                    <li>Coordination housekeeping pour appartements de plage, villas sur les hauteurs et biens mixtes.</li>
                    <li>Support conciergerie pour les repas, transferts, réservations et conseils de destination.</li>
                    <li>Partenaires locaux de confiance capables d’agir quand le timing est critique.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="sveti-vlas-ops-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Avantage opérationnel</p>
                    <h2 id="sveti-vlas-ops-fr">Les meilleurs services de conciergerie donnent au bien une impression très composée.</h2>
                  </div>
                  <p>Le client ne voit généralement pas la couche de coordination, mais il ressent immédiatement son effet. Quand l’arrivée est bien synchronisée, que le bien est prêt et que le support local répond, le séjour paraît maîtrisé.</p>
                  <p>Le même système fonctionne pour différents types de biens - appartement marina, villa sur les hauteurs ou logement familial - avec un standard commun et des détails adaptés au lieu.</p>
                </section>

                <section class="trust-layer" aria-labelledby="sveti-vlas-faq-fr">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Questions fréquentes</p>
                    <h2 id="sveti-vlas-faq-fr">Questions des équipes et des hôtes à Sveti Vlas.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Peut-on soutenir des biens près de la marina ?</h3>
                      <p>Oui. Les arrivées marina exigent un timing précis et une coordination fiable des partenaires.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Est-ce utile pour les villas et appartements sur les hauteurs ?</h3>
                      <p>Oui. Les différents types de biens peuvent partager le même modèle opérationnel avec leurs propres besoins.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Aide-t-il à gérer la demande saisonnière ?</h3>
                      <p>Oui. La demande saisonnière est plus simple à gérer lorsque les demandes et les partenaires sont visibles dans un seul workflow.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/concierge-bulgaria", "label": "Conciergerie en Bulgarie", "description": "Lisez la stratégie plus large pour la conciergerie sur la mer Noire."},
                {"href": "/guest-experience-services", "label": "Services d’expérience client", "description": "Voyez comment Sveti Vlas s’intègre dans le parcours client global."},
                {"href": "/property-management-bulgaria", "label": "Gestion immobilière en Bulgarie", "description": "Reliez l’opération locale à l’ensemble du portefeuille."},
                {"href": "/request-service", "label": "Demander un support", "description": "Lancez une demande et faites-la passer dans le workflow opérationnel."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Services de conciergerie à Sveti Vlas",
                "url": "https://blackseaconnect.com/sveti-vlas-concierge-services",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Sveti Vlas",
                "serviceType": [
                    "services de conciergerie",
                    "guest concierge",
                    "coordination des arrivées",
                    "partenaires locaux de confiance",
                ],
                "description": "Services de conciergerie à Sveti Vlas pour les biens côtiers près de la marina, les appartements en front de mer et les villas sur les hauteurs qui ont besoin d’un support fiable et d’une coordination locale.",
            },
        },
        "ru": {
            "title": "BlackSea Connect | Консьерж-услуги в Свети-Власе",
            "description": "Консьерж-услуги в Свети-Власе для прибрежных объектов рядом с мариной, апартаментов у моря и вилл на холмах, которым нужна надёжная поддержка гостей и локальная координация.",
            "h1": "Консьерж-услуги в Свети-Власе для прибрежной недвижимости и marina-пребываний",
            "eyebrow": "SEO-страница",
            "intro": "Консьерж-услуги в Свети-Власе должны отражать местный ритм: движение в марине, прибрежные маршруты и комплексы, где останавливаются семьи, яхтенные путешественники и постоянные гости.",
            "keywords": ["консьерж-услуги Свети-Влас", "guest concierge", "управление недвижимостью Чёрное море", "координация прибытия", "проверенные местные партнёры"],
            "ctas": [
                {"label": "Запросить поддержку Свети-Влас", "href": "/request-service", "class": "button--primary"},
                {"label": "Изучить консьерж-сервисы", "href": "/concierge-bulgaria", "class": "button--secondary"},
                {"label": "Посмотреть партнёров", "href": "/network", "class": "button--tertiary"},
            ],
            "content_html": dedent(
                """
                <section class="trust-layer" aria-labelledby="sveti-vlas-local-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Локальный контекст</p>
                    <h2 id="sveti-vlas-local-ru">Свети-Влас - место, где консьерж-работа следует очень конкретному прибрежному ритму.</h2>
                  </div>
                  <p>Трафик в марине, пляжный ритм, сезонность и ожидания гостей, которые приезжают на машине, трансфером или на лодке, требуют локального понимания. BlackSea Connect управляет этой сложностью в одном workflow.</p>
                  <p>Координация прибытия, обновления housekeeping и dispatch партнёров происходят в едином процессе, чтобы пребывание выглядело спокойным и премиальным.</p>
                </section>

                <section class="credibility-layer" aria-labelledby="sveti-vlas-needs-ru">
                  <div class="section-heading">
                    <p class="section-heading__eyebrow">Что нужно гостям</p>
                    <h2 id="sveti-vlas-needs-ru">Самые частые запросы - операционные, а не декоративные.</h2>
                  </div>
                  <p>В прибрежной локации мелочи имеют большой вес. Задержанный трансфер меняет начало проживания. Поздний housekeeping влияет на check-in. Пропущенная локальная рекомендация лишает гостя ощущения места.</p>
                  <p>BlackSea Connect держит эти моменты под контролем через workflow заявок, который направляет задачу нужному человеку и сохраняет её видимой до завершения.</p>
                  <ul>
                    <li>Координация прибытия для marina-аривалов, частных водителей и поздних check-in.</li>
                    <li>Housekeeping-координация для пляжных апартаментов, вилл на холмах и смешанных объектов.</li>
                    <li>Concierge support для ужинов, транспорта, бронирований и ориентации в месте.</li>
                    <li>Проверенные местные партнёры, которые могут быстро среагировать, когда тайминг критичен.</li>
                  </ul>
                </section>

                <section class="trust-layer" aria-labelledby="sveti-vlas-ops-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Операционное преимущество</p>
                    <h2 id="sveti-vlas-ops-ru">Лучшие консьерж-услуги делают объект спокойным и собранным.</h2>
                  </div>
                  <p>Гость обычно не видит слой координации, но сразу чувствует его результат. Когда прибытие синхронизировано, объект готов, а локальная поддержка реагирует быстро, проживание выглядит уверенным.</p>
                  <p>Тот же system подходит для объектов разных типов - marina-apartment, villa на холме или семейное жильё - с общим стандартом и адаптацией к месту.</p>
                </section>

                <section class="trust-layer" aria-labelledby="sveti-vlas-faq-ru">
                  <div class="section-heading section-heading--trust">
                    <p class="section-heading__eyebrow">Частые вопросы</p>
                    <h2 id="sveti-vlas-faq-ru">Вопросы команд и хостов в Свети-Власе.</h2>
                  </div>
                  <div class="trust-grid">
                    <article class="trust-card">
                      <h3>Можно ли поддерживать объекты рядом с мариной?</h3>
                      <p>Да. Marina-arrivals требуют точного тайминга и надёжной координации партнёров.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Полезно ли это для вилл и апартаментов на холмах?</h3>
                      <p>Да. Разные типы объектов могут использовать один и тот же операционный model с разными нуждами.</p>
                    </article>
                    <article class="trust-card">
                      <h3>Помогает ли при сезонном спросе?</h3>
                      <p>Да. Сезонный спрос проще управлять, когда заявки и партнёры видны в одном workflow.</p>
                    </article>
                  </div>
                </section>
                """
            ).strip(),
            "related_links": [
                {"href": "/concierge-bulgaria", "label": "Консьерж-услуги в Болгарии", "description": "Прочитайте более широкую стратегию консьерж-услуг по Чёрному морю."},
                {"href": "/guest-experience-services", "label": "Сервисы guest experience", "description": "Посмотрите, как Свети-Влас вписывается в общий путь гостя."},
                {"href": "/property-management-bulgaria", "label": "Управление недвижимостью в Болгарии", "description": "Свяжите локальную операцию с полной портфельной системой."},
                {"href": "/request-service", "label": "Запросить поддержку", "description": "Запустите запрос и проведите его через операционный workflow."},
            ],
            "service_schema": {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Консьерж-услуги в Свети-Власе",
                "url": "https://blackseaconnect.com/sveti-vlas-concierge-services",
                "provider": {"@type": "Organization", "name": "BlackSea Connect", "url": "https://blackseaconnect.com/"},
                "areaServed": "Свети-Влас",
                "serviceType": [
                    "консьерж-услуги",
                    "guest concierge",
                    "координация прибытия",
                    "проверенные местные партнёры",
                ],
                "description": "Консьерж-услуги в Свети-Власе для прибрежных объектов рядом с мариной, апартаментов у моря и вилл на холмах, которым нужна надёжная поддержка гостей и локальная координация.",
            },
        },
    },
}


def resolve_seo_landing_page(path, lang):
    page = deepcopy(SEO_LANDING_PAGES[path])
    page.update(_SEO_PAGE_UI_COPY.get(lang, _SEO_PAGE_UI_COPY["en"]))
    page.update(SEO_LANDING_PAGE_LOCALES.get(path, {}).get(lang, {}))
    page.update(SEO_LANDING_PAGE_LOCALE_OVERRIDES.get(path, {}).get(lang, {}))
    page["lang"] = lang if lang in SEO_SUPPORTED_LANGS else "en"
    return page
