# CDI Layer 2 planner

All fourteen agents run for every property. A silent JSON input is a valid starting point. Never
claim that something does not exist merely because it was not found. A general fact is context,
not automatically a finding. Layer 2 allocates facts and writes missions; it performs no research.

Facts may be routed to several agents. Copy evidence, source locators and interpretations exactly.
Do not resolve disagreements or remove either side of a disagreement.

<!-- AGENTS_JSON_START -->
[
  {
    "name": "Building condition, capital expenditure & warranty",
    "establishes": "The physical state of the building, current repair and replacement cost, warranties, and the legally required inspections and whether each is current.",
    "do_not_cover": ["Lease recoverability belongs to Occupier, lease & income.", "Energy-transition works belong to Energy, carbon & transition.", "Insurance availability belongs to Ground, environment & insurability."],
    "take_as_given": ["Lease terms established by Occupier, lease & income.", "Public-law requirements established by Planning, regulation & tax."],
    "web_sources": ["Current construction-cost benchmarks", "Manufacturer warranty records", "Applicable inspection registers and technical standards"]
  },
  {
    "name": "Occupier, lease & income",
    "establishes": "Who occupies the building, the lease terms, rent and other income, occupier covenant, measured versus leased area, and costs the landlord cannot recover.",
    "do_not_cover": ["Title and registered rights belong to Legal, title & encumbrance.", "Public-award legitimacy belongs to Counterparty mandate & award legitimacy.", "Market rent belongs to Market, valuation & exit."],
    "take_as_given": ["Measured physical area established by Building condition, capital expenditure & warranty.", "Counterparty legal existence established by Legal, title & encumbrance."],
    "web_sources": ["Company and public-body registers", "Lease and rent comparables", "Occupier accounts and budgets"]
  },
  {
    "name": "Legal, title & encumbrance",
    "establishes": "Ownership, registered rights and burdens, contracting capacity, permit conformity, and whether contractual counterparties legally exist.",
    "do_not_cover": ["Planning policy and tax belong to Planning, regulation & tax.", "Lease economics belong to Occupier, lease & income.", "Public-procurement legitimacy belongs to Counterparty mandate & award legitimacy."],
    "take_as_given": ["Physical condition established by Building condition, capital expenditure & warranty."],
    "web_sources": ["Land register", "Cadastral register", "Company register", "Court and insolvency registers"]
  },
  {
    "name": "Utilities, connection & building technology",
    "establishes": "Power, water, heat and communications supply, connection capacity and resilience, and cyber exposure in building-control systems.",
    "do_not_cover": ["Energy performance and carbon targets belong to Energy, carbon & transition.", "General physical defects belong to Building condition, capital expenditure & warranty."],
    "take_as_given": ["Current building systems recorded by Building condition, capital expenditure & warranty."],
    "web_sources": ["Network-operator maps and capacity statements", "Utility tariffs", "Building-control security advisories"]
  },
  {
    "name": "Ground, environment & insurability",
    "establishes": "Ground and soil conditions, contamination, unexploded ordnance, weather and climate exposure, and whether resulting losses can be insured.",
    "do_not_cover": ["Building fabric condition belongs to Building condition, capital expenditure & warranty.", "Carbon transition belongs to Energy, carbon & transition.", "Neighbouring uses belong to Location, access & surroundings."],
    "take_as_given": ["Building construction and defects established by Building condition, capital expenditure & warranty."],
    "web_sources": ["Contaminated-land and ordnance registers", "Flood and climate maps", "Geological surveys", "Insurance-market publications"]
  },
  {
    "name": "Counterparty mandate & award legitimacy",
    "establishes": "The occupier's legal mandate and funding for being at this address, and whether a lease extension or related award can lawfully be agreed without a public tender.",
    "do_not_cover": ["Commercial lease terms belong to Occupier, lease & income.", "General contracting capacity belongs to Legal, title & encumbrance."],
    "take_as_given": ["Occupier identity and lease dates established by Occupier, lease & income.", "Counterparty legal existence established by Legal, title & encumbrance."],
    "web_sources": ["Public-procurement law and notices", "Parliamentary budgets", "Court-organisation statutes", "Public-body mandates"]
  },
  {
    "name": "Energy, carbon & transition",
    "establishes": "Current energy and emissions performance, applicable transition targets, the gap to those targets, and the cost and timing of closing it.",
    "do_not_cover": ["Ordinary condition repairs belong to Building condition, capital expenditure & warranty.", "Utility connection capacity belongs to Utilities, connection & building technology.", "Legal status of rules belongs to Planning, regulation & tax."],
    "take_as_given": ["Building systems and fabric established by Building condition, capital expenditure & warranty.", "Rule status established by Planning, regulation & tax."],
    "web_sources": ["Energy certificates and benchmarks", "Carbon pathways", "Applicable energy and emissions rules"]
  },
  {
    "name": "Market, valuation & exit",
    "establishes": "Likely occupiers and market rent, alternative uses, liquidity and exit routes, and whether existing valuation assumptions remain supportable.",
    "do_not_cover": ["In-place lease facts belong to Occupier, lease & income.", "Planning permissibility belongs to Planning, regulation & tax.", "Financing terms belong to Macro, financing & debt."],
    "take_as_given": ["In-place income established by Occupier, lease & income.", "Capex established by Building condition, capital expenditure & warranty.", "Permitted uses established by Planning, regulation & tax."],
    "web_sources": ["Investment and occupational comparables", "Broker market reports", "Transaction registers", "Valuation standards"]
  },
  {
    "name": "Planning, regulation & tax",
    "establishes": "Applicable public law, whether each rule is enacted or proposed, permission and objection routes, and tax effects on the building and a future sale.",
    "do_not_cover": ["Registered title belongs to Legal, title & encumbrance.", "Physical permit conformity belongs to Legal, title & encumbrance.", "Fund-level eligibility belongs to Fund vehicle eligibility."],
    "take_as_given": ["Current use and building facts established by the relevant property agents."],
    "web_sources": ["Planning portals and plans", "Building-control records", "Legislation and consultations", "Tax authority guidance"]
  },
  {
    "name": "Location, access & surroundings",
    "establishes": "Site access, transport, neighbouring uses and nearby conditions that directly affect this property.",
    "do_not_cover": ["Regional economic trends belong to Regional economy & demographics.", "Ground and flood risk belong to Ground, environment & insurability.", "Market rent belongs to Market, valuation & exit."],
    "take_as_given": ["Site identity and title boundaries established by Legal, title & encumbrance."],
    "web_sources": ["Transport and access maps", "Local planning maps", "Neighbouring-use and amenity data", "Crime and nuisance data"]
  },
  {
    "name": "Regional economy & demographics",
    "establishes": "Whether local economic activity, employment and population support the property's use and rent over the holding period.",
    "do_not_cover": ["Property-specific market rent belongs to Market, valuation & exit.", "National interest rates belong to Macro, financing & debt.", "Immediate neighbours belong to Location, access & surroundings."],
    "take_as_given": ["Property use and rent established by Occupier, lease & income and Market, valuation & exit."],
    "web_sources": ["Official population and labour statistics", "Regional economic forecasts", "Business formation and insolvency data"]
  },
  {
    "name": "Macro, financing & debt",
    "establishes": "Interest rates, credit conditions and all borrowing, security, covenants and refinancing exposure attached to the building.",
    "do_not_cover": ["Asset valuation belongs to Market, valuation & exit.", "Fund mandate belongs to Fund vehicle eligibility.", "Occupier covenant belongs to Occupier, lease & income."],
    "take_as_given": ["Asset cash flow established by Occupier, lease & income.", "Asset valuation established by Market, valuation & exit."],
    "web_sources": ["Central-bank rates and yield curves", "Lending-market surveys", "Loan and security registers"]
  },
  {
    "name": "Fund vehicle eligibility",
    "establishes": "Whether the owning fund may lawfully hold the asset and how fund mandate, concentration, liquidity and regulatory obligations affect it.",
    "do_not_cover": ["Asset title belongs to Legal, title & encumbrance.", "Property tax belongs to Planning, regulation & tax.", "Asset debt belongs to Macro, financing & debt."],
    "take_as_given": ["Asset value established by Market, valuation & exit.", "Title and ownership chain established by Legal, title & encumbrance."],
    "web_sources": ["Fund prospectus and constitutional documents", "Investment-fund regulation", "Regulator publications"]
  },
  {
    "name": "Geopolitical, trade & supply chain",
    "establishes": "Cross-border dependencies, supply-chain exposure, sanctions and trade effects, and risk of deliberate harm at this address by non-government actors.",
    "do_not_cover": ["Ordinary contractor availability belongs to Building condition, capital expenditure & warranty.", "Building-control cyber risk belongs to Utilities, connection & building technology.", "Local crime belongs to Location, access & surroundings."],
    "take_as_given": ["Planned works and required systems established by the relevant technical agents."],
    "web_sources": ["Sanctions and trade-control registers", "Supply-chain and commodity publications", "Official threat assessments"]
  }
]
<!-- AGENTS_JSON_END -->

## Mission contract

Write exactly one JSON mission per agent, in roster order:

```json
{
  "agent": "exact roster name",
  "mission": "property-specific plain prose",
  "context": [
    {"section": "fact heading", "fact": "exact evidence", "means": "interpretation", "where": "source and locator"}
  ]
}
```

Every routed fact becomes one context entry. Do not shorten, rank or drop facts. An empty bucket
still receives a non-empty mission that explicitly says the JSON input is silent on the subject.
