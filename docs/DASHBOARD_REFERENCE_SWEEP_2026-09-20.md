# Analytics dashboards — reference sweep

Research date: 2026-09-20

This is a reference sweep of the standard analytics screen, not a proposed layout.

**Counting rule:** “numbers on the first screen” means named headline/stat values and their comparison percentages. I do not count chart-axis ticks, dates, timestamps, or numbers buried in long tables. **Colour count** means distinct data/accent hues, excluding black, white, grey and anti-aliased shades. For “above the fold,” I used a normal laptop-sized viewport, roughly 1366×768 to 1440×900. Exact cut-offs move with viewport height.

---

## Plausible

**Sources looked at:**

- Public live demo: <https://plausible.io/plausible.io>
- Current Dashboard overview, updated 2026-07-13: <https://plausible.io/docs/guided-tour>
- Current comparison documentation, updated 2026-09-09: <https://plausible.io/docs/compare-stats>
- Metric definitions: <https://plausible.io/docs/metrics-definitions>
- Bot and spam filtering: <https://plausible.io/docs/bot-traffic-filtering>
- Dashboard appearance: <https://plausible.io/docs/dashboard-appearance>
- Dashboard FAQ: <https://plausible.io/docs/dashboard-faq>

The live demo was opened for this sweep. The current documentation was used to pin down behaviour that is not exposed reliably through a text capture of the dynamic demo.

### 1. The first screen

The eye lands on the **top metric row and the large time-series graph immediately under it**. Within the row, **Unique visitors** is the first headline number.

The standard top graph exposes six traffic/engagement metrics: **Unique visitors, Total visits, Total pageviews, Views per visit, Bounce rate, Visit duration**. A small **current visitors** count is also available in the dashboard header area and opens the realtime view.

On a laptop, the six-metric row and main graph are above the fold. Depending on viewport height, the beginning of the lower breakdown area can also appear. The detailed Sources, Pages, Locations, Devices and conversion sections continue below.

### 2. How many numbers on the first screen

There are **6 primary KPI numbers** in the top metric row. Counting the small current-visitors readout gives **7 headline/realtime numbers** before chart-axis labels.

They are grouped as one horizontal metric row above one large chart; there is no persistent analytics sidebar taking up the content area.

Comparison is optional. When enabled, **the metric cards show percentage changes with up/down arrows**, and the main chart draws both periods. Hovering a chart point gives the values and percentage change. The cards do **not** use mini sparklines.

### 3. How it separates people from bots

Plausible **filters known bots, crawlers, referrer spam and other non-human traffic before it reaches the normal statistics**. Its current filtering documentation describes several layers, including user-agent checks, data-centre IP ranges and traffic-pattern checks.

There is **no human-versus-bot split on the first screen** and no bot-volume number beside the human traffic totals. The ordinary dashboard shows the traffic left after filtering.

### 4. How it explains a stat

The standard dashboard relies mainly on **separate metric documentation**, not a visible ⓘ beside every top metric. The chart itself has hover values, but that is a value tooltip rather than a definition tooltip.

Plausible’s metric definition for Unique Visitors is:

> “The number of people who visited your site.” — Plausible, *Metrics definitions*

### 5. How it handles a blank

The **exact current empty-state copy is not verified**.

Plausible’s dashboard FAQ says that when it has not recorded any visits yet, the dashboard can show **a blinking green dot instead of the dashboard**. That documents the state, but I could not verify the exact current on-screen sentence shown with it.

### 6. What it does with time

The date picker is in the **top-right** of the dashboard. Plausible documents ranges including Today, realtime and longer rolling/calendar periods. **The default range on a fresh public-demo visit is not verified.**

Changing the date range changes the top metrics and the main chart together, and the same dashboard filters apply across the lower reports. Comparison can be Previous period, Year over year or a Custom period. The chart interval can also be changed separately from the date range.

### 7. Contrast and hierarchy

The **metric row is large**, the **main time-series chart is the dominant block**, and the detailed breakdowns are quieter beneath it.

In the cited standard light appearance, the main data treatment uses roughly **two accent/status hues** before comparison: an indigo/purple data colour and a green realtime/status cue, plus neutrals. Comparison adds a second line treatment and up/down status colours.

Plausible supports **Light, Dark and System** appearance modes; System is documented as an option.

### 8. One thing better; one thing worse

**Better:** It keeps six core traffic and engagement metrics plus the main trend graph in one compact, continuous dashboard without a persistent reporting sidebar.

**Worse:** Bot filtering is almost completely invisible as a quantity, so the first screen gives no sense of how much traffic was removed as non-human.

---

## Fathom

**Sources looked at:**

- Live demo entry: <https://app.usefathom.com/demo>
- Current dashboard documentation and documented dashboard screenshot: <https://usefathom.com/docs/start/dashboard>
- Bot detection documentation: <https://usefathom.com/docs/features/bot-detection>
- April 2026 bot-banning dashboard update: <https://usefathom.com/changelog/apr2026-bot-banning>
- No-data/troubleshooting documentation: <https://usefathom.com/docs/troubleshooting/not-working>

The live demo was opened. On 2026-09-20 it resolved to Fathom’s shared **Hilarious Platypus** dashboard with `range=last_7_days`, so the live-demo range at the time of this sweep was **Last 7 days**. The first-party dashboard screenshot in the help article shows the same overall structure with sample data.

### 1. The first screen

The eye lands on the **dark totals strip** across the top of the analytics area. The first number at the far left is the **Realtime** count; immediately beside it is the larger traffic measure labelled **People/Site visitors**.

Above the fold on a laptop: site/date controls, the dark totals strip, the large trend graph, and at least the beginning of the Pages and Referrers tables. The lower rows of those tables and further breakdowns continue below.

### 2. How many numbers on the first screen

The documented populated dashboard screenshot shows **6 large totals** in the strip: **Realtime, People, Views, Avg time on site, Bounce rate, Event completions**. Fathom’s current docs say Event completions is available when the site has at least one event, so a site without events can have **5** instead.

Since April 2026, Fathom also puts a **bot icon in the toolbar with the total blocked bot requests for the selected date range**. That is an additional smaller numerical readout outside the main totals strip.

The large metrics are grouped in one strip, not separate floating cards. Comparison is off until added. Once enabled, **every metric across the dashboard shows the change**, with text such as a percentage versus the previous period. The graph shows current and comparison periods together. There are no KPI sparklines in the main totals strip.

### 3. How it separates people from bots

Fathom separates non-human traffic **at ingestion** so blocked bot traffic does not enter the normal human traffic totals.

Unlike the other simple analytics dashboards here, Fathom also exposes **a blocked-bot count directly in the dashboard toolbar**. Clicking it shows a bot breakdown by classification and top countries.

It still does **not** put human traffic and bot traffic side by side as equal headline metrics. The human totals remain the primary strip; the bot count is a secondary toolbar item.

### 4. How it explains a stat

The dashboard documentation supplies the definitions. I did not verify a persistent ⓘ definition control beside each headline number in the normal dashboard.

Fathom defines Site visitors as:

> “Site visitors is the number of unique individuals who visited your website during a 24-hour period.” — Fathom, *Dashboard explained*

### 5. How it handles a blank

**Not verified.** Fathom documents troubleshooting for a dashboard that is not receiving visits, but I could not verify the exact current empty-dashboard sentence shown to a user with no data.

### 6. What it does with time

The current public demo opened at **Last 7 days**. The date picker controls the dashboard range. Fathom also lets a user drag across the graph to zoom into a date range.

Comparison is added beside the date picker and can use Previous period, Previous month, Previous quarter, Previous year or a custom range. Once a comparison is chosen, the metric strip and chart change together; the current docs say every metric across the dashboard shows the change.

The Realtime value remains a realtime measure by definition rather than becoming a historical total.

### 7. Contrast and hierarchy

The dominant visual object is the **near-black totals strip with very large light numbers**. The chart is second. Breakdown tables are quieter.

The cited dashboard screenshot uses about **two data hues** in the graph — purple and blue/cyan — plus the black/white/grey interface. Comparison can add status treatment, but the base screenshot is restrained.

Fathom supports **Auto/System, Light and Dark**. Its documentation says the default “Automagic” setting follows the system colour preference.

### 8. One thing better; one thing worse

**Better:** It is the only one of these five whose standard analytics dashboard is documented as showing the total number of blocked bot requests directly in the toolbar.

**Worse:** Its standard top totals do not include a separate Visits/Sessions total, so repeat sessions are less immediately visible than in Plausible or Umami.

---

## Umami

**Sources looked at:**

- Public shared demo URL checked: <https://eu.umami.is/share/LGazGOecbDtaIwDr/umami.is>
- Current first-party shared-dashboard screenshot/documentation: <https://docs.umami.is/docs/enable-share-url>
- Direct documented screenshot used for the first-screen reading: <https://docs.umami.is/images/docs/share-details.png>
- Metric definitions: <https://docs.umami.is/docs/metric-definitions>
- Bot-check configuration: <https://docs.umami.is/docs/environment-variables>
- Filtering/date behaviour: <https://docs.umami.is/docs/filters>
- Insights/comparison documentation: <https://docs.umami.is/docs/insights>

The public demo URL was checked, but the research browser could not render its client-side dashboard. I therefore used Umami’s current first-party shared-dashboard screenshot for the visual sweep and current docs for behaviour. Where the demo itself could not be verified, I say so.

### 1. The first screen

The eye lands on the **five-card KPI row**. The first card is **Visitors**. Under that is one large blue time-series/bar chart.

In the cited current shared-dashboard screenshot, a laptop first screen contains the left navigation, site/filter/date controls, all five KPI cards, and the full main chart. The lower reports are below the captured first screen.

### 2. How many numbers on the first screen

There are **5 primary KPI numbers**: **Visitors, Visits, Views, Bounce rate, Visit duration**.

Each of the five cards in the cited screenshot also carries a percentage change, so the row contains **10 numerical readouts** if the five deltas are counted. They are grouped as five equal cards. There are no mini sparklines inside those cards.

The cited screenshot already shows direction/percentage comparisons under each KPI. Umami also has comparison analysis in Insights.

### 3. How it separates people from bots

Umami’s documented server configuration says **bots are excluded from statistics by default**; `DISABLE_BOT_CHECK` disables that checking.

The normal Overview first screen does **not** show a bot count or a people-versus-bots split. The result is similar to Plausible: the visible dashboard presents the traffic left after bot exclusion.

### 4. How it explains a stat

Definitions live in the documentation. I did not verify an inline ⓘ beside each top KPI in the current Overview screenshot.

Umami’s definition for Views is:

> “The total number of events collected from your visitors.” — Umami, *Metric definitions*

### 5. How it handles a blank

**Not verified.** I could not verify current first-party empty-state copy for a new site or an uncomputable metric.

### 6. What it does with time

The cited first-party shared-dashboard screenshot shows **Last 7 days**, but **the fresh default range is not verified**.

The date control sits at the top of the page. Umami’s filtering documentation treats the selected date range and filters as page-level context, so the Overview cards and chart move together with that context. Separate Boards likewise use a date selector that changes the period for all components on that board.

### 7. Contrast and hierarchy

The five **large white KPI cards** form the strongest first row; the **large chart** is the second level; the left navigation and controls are quieter.

In the cited screenshot, there are **two clear chromatic hues** on the first screen: blue for the chart and red/pink for the comparison changes, plus neutrals. A positive-delta state can introduce status colour, but that was not present in the cited screenshot.

Dark mode is supported by the Umami project, but I did not verify the current theme control from the public demo during this sweep.

### 8. One thing better; one thing worse

**Better:** Its cited Overview puts a percentage change directly under each of all five primary KPIs, so period direction is readable without moving attention to the chart.

**Worse:** The persistent left navigation consumes more horizontal space than the one-page Plausible and Fathom dashboards, leaving a narrower chart area at the same laptop width.

---

## Cloudflare Web Analytics

**Sources looked at:**

- Current high-level metrics documentation and current Web Analytics overview screenshot: <https://developers.cloudflare.com/web-analytics/data-metrics/high-level-metrics/>
- Current filters/time documentation: <https://developers.cloudflare.com/web-analytics/configuration-options/filters/>
- Current dimensions documentation, including Exclude Bots: <https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/>
- Current setup/no-data timing note: <https://developers.cloudflare.com/web-analytics/get-started/>
- Cloudflare dashboard appearance settings: <https://developers.cloudflare.com/fundamentals/user-profiles/customize-account/>
- Original Web Analytics launch article for historical comparison: <https://blog.cloudflare.com/privacy-first-web-analytics/>
- Current Web Analytics/RUM background: <https://blog.cloudflare.com/the-rum-diaries-enabling-web-analytics-by-default/>

For the first-screen reading I used the **current screenshot embedded in Cloudflare’s current high-level-metrics documentation**, not the older launch screenshot.

### 1. The first screen

The largest object is the **central Visits summary chart**. The selected **Visits** card on the left supplies the first large number, and the same Visits total is repeated at the top of the main panel.

In the current documented screenshot, the full laptop first screen contains a left rail with **Visits, Page views, Page load time and Core Web Vitals**, plus the central Visits summary, filter control, time selector and the chart. Quick Actions also begin below the metric rail.

### 2. How many numbers on the first screen

In the current documented screenshot there are **3 primary numeric card values** in the left rail: Visits, Page views and Page load time. Each has a percentage change, adding **3 comparison percentages**. The selected Visits total is repeated once in the main panel. That makes **7 visible headline numerical readouts** before chart-axis labels.

The **Core Web Vitals** card adds four labelled bars — LCP, INP, FID and CLS in the cited screenshot — but shows no numeric values in that card.

The left cards include **small sparklines**, unlike Plausible, Fathom and Umami’s headline cards. The percentage deltas are shown directly beside the card values.

### 3. How it separates people from bots

The Web Analytics dimensions include an **Exclude Bots** filter. Setting that dimension to Yes removes identified bots to make the result closer to real-user traffic.

There is **no people-versus-bots split on the standard Web Analytics first screen**. Bot analysis exists elsewhere in Cloudflare — for example Security Analytics can classify automated, likely automated, likely human and verified-bot traffic — but that is not the Web Analytics overview shown here.

### 4. How it explains a stat

Cloudflare does more inline explanation than the other compact dashboards. The current screenshot places a sentence directly under **Visits summary** explaining what a visit means.

The documented screenshot says:

> “When someone navigates to your website, either directly or from an external referer. One visit can consist of multiple page views.” — Cloudflare Web Analytics screenshot

There is also separate metric documentation.

### 5. How it handles a blank

The **exact empty-state sentence is not verified**. Cloudflare’s current setup documentation says that after Web Analytics is enabled, **data may take a few minutes to appear**. That tells the user what delay to expect, but I did not verify the exact no-data panel copy.

### 6. What it does with time

Cloudflare documents **Previous 24 hours** as the default Web Analytics range, and the current screenshot shows that value in the top-right selector.

The range is changed from the dropdown above the graph. The graph can also be dragged to select a custom interval. Filters and the selected period apply to the Web Analytics view, so the metric rail and central summary are working from the same selected context.

### 7. Contrast and hierarchy

The **central chart is largest**. The left metric rail is second. The individual card labels, Quick Actions and dimension tabs are quieter.

The cited current screenshot uses **two main accent/status hues**: blue for selected borders, sparklines and the main chart; green for change indicators and Core Web Vitals status bars, plus neutrals.

The wider Cloudflare dashboard supports **Dark, Light and Use system** appearance modes.

### 8. One thing better; one thing worse

**Better:** It is the only one of these five whose standard Web Analytics first screen puts page-load performance/Core Web Vitals beside the traffic trend rather than making performance a separate reporting destination.

**Worse:** Its standard high-level traffic set does not give the same explicit unique-person headline metric that Plausible, Fathom, Umami and Matomo expose.

---

## Matomo

**Sources looked at:**

- Current Matomo 5.10.0 changelog and official new-UI screenshot, dated 2026-05-03: <https://matomo.org/changelog/matomo-5-10-0/>
- Dashboard guide: <https://matomo.org/guide/reports/dashboard/>
- Dashboard/widget customisation: <https://matomo.org/faq/dashboards/create-dashboards-and-customise-widgets-and-layout/>
- Default-dashboard behaviour: <https://matomo.org/faq/how-to/faq_26289/>
- Help/tooltips: <https://matomo.org/faq/reports/accessing-helpful-advice-within-matomo/>
- Generic no-data state: <https://matomo.org/faq/troubleshooting/faq_58/>
- Default date selection: <https://matomo.org/faq/how-to/faq_72/>
- Bot tracking/exclusion: <https://matomo.org/faq/new-to-piwik/faq_63/>
- AI Assistants guide: <https://matomo.org/guide/reports/ai-assistants/>
- AI Agent Overview: <https://matomo.org/faq/reports/ai-agent-overview-report/>
- AI chatbot terminology and limits: <https://matomo.org/faq/reports/what-are-ai-assistants-in-matomo/>
- AI chatbot telemetry setup: <https://matomo.org/faq/how-to/install-ai-chatbot-tracking/>
- Official demo entry checked: <https://demo.matomo.cloud/>

The official demo entry was opened, but its dashboard is JavaScript-driven and was not available to the text capture. For the visual sweep I therefore used Matomo’s **current 5.10.0 official screenshot**, as requested.

### 1. The first screen

Matomo does **not have one fixed first headline number**, because its dashboard is a collection of configurable widgets.

In the current 5.10 screenshot, the strongest central object is the **Visits Over Time** chart. To its left is a tall **Visits in real-time** widget; to its right is a **Visitor Map** with **11,558 unique visitors** in the sample screenshot.

Above the fold in that screenshot: the top controls, Visits in real-time, Visits Over Time and Visitor Map are fully established; the next row begins with **Movers and Shakers** and **Channel Types**. The lower portions of the long widgets continue below.

### 2. How many numbers on the first screen

There is **no fixed product-wide number** because widgets can be added, removed and rearranged.

For a concrete reference, the cited Matomo 5.10 screenshot contains **15 clearly readable metric values before counting chart axes, dates and timestamps**: four values in the two realtime summary rows, one unique-visitors map total, two visible Movers and Shakers changes, and eight percentage/count values in the visible Channel Types rows.

The numbers are grouped inside independent report widgets rather than one stat row. Comparisons are available in Matomo reports/date comparisons, but the cited default-style 5.10 dashboard screenshot is not presented as a uniform “every card has a prior-period arrow” view. **A single universal first-screen comparison treatment is not verified because the widget mix is configurable.**

### 3. How it separates people from bots

By default, Matomo **excludes requests it identifies as bots from normal visitor analytics** unless bot tracking is intentionally enabled.

Matomo now goes further than the other products in this sweep outside the standard dashboard: it has dedicated **AI Agent** and **AI Chatbot** reporting. The AI Agent Overview can compare AI-agent visits with human visits; AI chatbot telemetry can be collected through supported server-side integrations and kept separate from ordinary visits.

That split is **not on the standard Dashboard first screen** shown in the current 5.10 screenshot.

One important distinction: the **AI Assistants** row visible under Channel Types in the current screenshot is an acquisition channel for visits referred from AI tools. It is not the same thing as crawler/scraper traffic. Matomo’s documentation separately distinguishes AI referrals, AI agents and AI chatbots, and says model-training/indexing crawlers are not part of the AI Agent/AI Chatbot reports.

### 4. How it explains a stat

Matomo has the most explicit general help machinery of the five: a **top-menu information/help control**, **hover tooltips on interactive elements**, and **inline ? icons** where more detail is available.

Its help documentation says:

> “While exploring the Matomo interface, you can usually hover above any interactive elements to reveal a short descriptive tooltip.” — Matomo FAQ

### 5. How it handles a blank

Matomo documents the generic report blank as:

> “There is no data for this report” — Matomo troubleshooting FAQ

Its AI chatbot setup documentation also documents a more specific **“No data collected”** state when chatbot telemetry has not yet been configured or received.

### 6. What it does with time

Matomo documents **Yesterday** as the default report period. Users can switch to other periods such as Today, current week/month and rolling ranges.

The current 5.10 screenshot places the date selector in the top control row. Date-scoped report widgets use that selected report period. Matomo also supports date-range comparison, but because dashboard contents are configurable, not every possible widget has an identical comparison presentation.

### 7. Contrast and hierarchy

The 5.10 interface has a **persistent left navigation** and a grid of similarly weighted white report cards. It has less of a single headline hierarchy than Plausible, Fathom, Umami or Cloudflare.

There is **no useful fixed colour count** for the first screen: the cited screenshot uses blue as the primary chart/accent colour, several blue shades in the map, and additional colours in country/browser/device icons. Widget contents can change the palette further.

Matomo 5.10 introduced **Dark Mode**; the documented default remains the light theme, and dark mode can be changed in personal settings.

### 8. One thing better; one thing worse

**Better:** Matomo is the only product in this set with documented dedicated AI Agent and AI Chatbot reports that can separate some automated AI activity from human traffic; those reports sit outside the standard first dashboard.

**Worse:** The configurable widget dashboard has the least stable first-screen hierarchy: there is no fixed headline-number count or fixed first metric across installations and users.

---

# Across all five

## Comparison table

| Product | First number / visual anchor | Numbers above the fold | Bot split shown? | Explanation method | Blank handling | Default range |
|---|---|---:|---|---|---|---|
| **Plausible** | Unique visitors in KPI row; large top graph directly below | 6 primary KPIs; 7 including current visitors | **No.** Bots are filtered before normal stats | Separate metric docs; chart value hover; no per-KPI definition control verified | Exact copy **not verified**; docs describe blinking green dot before any visits are recorded | **Not verified** |
| **Fathom** | Realtime is first numeral in the dark totals strip; People/Site visitors is next | 5 standard traffic/engagement totals, or 6 when Event completions is present; plus smaller blocked-bot count in toolbar | **Partly.** Blocked-bot total is visible, but no human-vs-bot headline split | Separate dashboard/metric docs; no per-KPI ⓘ verified | **Not verified** | **Last 7 days in the live public demo on 2026-09-20** |
| **Umami** | Visitors, first of five KPI cards | 5 primary KPI values + 5 percentage deltas in cited screenshot = 10 numerical readouts | **No.** Bots excluded by default | Separate metric docs; no inline KPI definition control verified | **Not verified** | **Not verified**; current first-party share screenshot shows Last 7 days |
| **Cloudflare Web Analytics** | Visits card/total; central Visits summary chart is largest | 3 numeric card values + 3 deltas + repeated selected total = 7; CWV card has bars without numbers | **No.** Exclude Bots is a filter; bot classification is elsewhere in Cloudflare | Inline definition sentence under selected metric + docs | Exact copy **not verified**; setup docs say data may take a few minutes to appear | **Previous 24 hours** |
| **Matomo** | No fixed first number; current 5.10 screenshot is anchored by Visits Over Time | Variable. Current 5.10 screenshot has 15 readable metric values by the counting rule | **No on the standard dashboard.** Dedicated AI Agent/Chatbot reports exist elsewhere | Hover tooltips, inline ? icons, top help/info, docs | **“There is no data for this report”**; AI chatbot reports also document “No data collected” | **Yesterday** |

## Three patterns all five share

1. **Time is global context near the top.** Each product puts a date/range control near the primary analytics view and ties the main trend view to that period. Matomo’s widgets are configurable, but its date selector still supplies the report period.

2. **A trend comes before the long breakdowns.** Their standard documented entry screens lead with headline traffic/performance information and a time-series view; sources, pages, geography, devices or other dimensions are lower on the page or inside subordinate widgets.

3. **None makes “human traffic versus automated traffic” two equal headline metrics on the standard first screen.** Plausible and Umami remove bots from ordinary stats; Cloudflare offers an Exclude Bots dimension and separate bot tooling; Fathom surfaces a blocked-bot count but not a peer split; Matomo has richer dedicated AI/bot reports but keeps them outside the standard Dashboard.

## Three things none of them puts first for a scraper/AI-crawler problem

These are specifically absent from the **standard first screen**. Some products, especially Matomo and Cloudflare, can expose parts of this elsewhere.

1. **Humans vs automated requests vs AI agents as three headline counts for the same time window.** A site owner worried about scraping would want the volume, percentage of total traffic and period-over-period change visible immediately. Fathom comes closest with its blocked-bot count, but it is not a side-by-side traffic split.

2. **The automated actors themselves.** None of the five standard first screens starts with “who is fetching me?” — for example crawler/agent family, declared User-Agent, verified operator status and request count. Matomo has dedicated AI reports elsewhere; Cloudflare has separate bot/security products; they are not the default Web Analytics/dashboard headline.

3. **What those automated actors took.** None of the five standard first screens leads with the pages/paths most fetched by automated agents, request volume per path, bytes/bandwidth consumed, and whether the requests were allowed, blocked or contrary to a crawler policy. Matomo can report AI chatbot content requests after separate telemetry setup, and Cloudflare has separate security/crawl tooling, but that information is not the first analytics view.

---

## Verification notes

- **Plausible:** live demo checked; current 2026 docs used for exact metric set, comparison behaviour, bot filtering and theme behaviour. Fresh-demo default date range was not reliably exposed, so it is marked not verified.
- **Fathom:** live demo checked and its current `last_7_days` range observed; current docs used for metrics and bot-toolbar behaviour. Exact no-data text was not found.
- **Umami:** public demo URL checked but could not be rendered by the research browser; first-party current shared-dashboard screenshot and docs used instead. Fresh-demo default range and exact blank text remain not verified.
- **Cloudflare:** current first-party Web Analytics screenshot used. The older 2020 launch screenshot was reviewed only as historical context and is not the basis for the current count above.
- **Matomo:** current May 2026 Matomo 5.10 UI screenshot used. The official demo entry was checked but its JavaScript dashboard did not render in the research capture. The first-screen count is therefore tied explicitly to the current official screenshot, not claimed as a universal Matomo layout.
