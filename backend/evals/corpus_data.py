"""Source of truth for the synthetic eval corpus.

Everything here is fictional. Ground truth in golden_v1.jsonl is derived from these values,
so a question's gold evidence is known by construction rather than LLM-guessed.
Distractor documents share structure and near-identical identifiers on purpose: they are what
makes dense-only retrieval fail on exact terms and give later phases something to improve.
"""

PRODUCTS: list[dict] = [
    {
        "slug": "atlas_sync", "name": "Atlas Sync", "version": "3.2.1", "release": "2025-03-18",
        "owner": "Platform Data Team", "purpose": "real-time replication of customer datasets between regions",
        "rate_limit": 600, "max_payload_mb": 25, "retention_days": 90,
        "auth": "OAuth 2.0 client credentials", "token_ttl_min": 45, "sla": "99.95",
        "primary_region": "eu-west-2", "dr_region": "us-east-1",
        "errors": {"E-4021": "the access token has expired", "E-5107": "the target shard is temporarily unavailable",
                   "E-4290": "the per-key rate limit was exceeded"},
    },
    {
        "slug": "atlas_relay", "name": "Atlas Relay", "version": "2.9.0", "release": "2025-01-27",
        "owner": "Edge Networking Team", "purpose": "forwarding webhook events to customer endpoints",
        "rate_limit": 1200, "max_payload_mb": 5, "retention_days": 30,
        "auth": "HMAC-signed requests", "token_ttl_min": 15, "sla": "99.90",
        "primary_region": "us-west-2", "dr_region": "eu-central-1",
        "errors": {"E-4022": "the request signature could not be verified", "E-5108": "the delivery queue is full",
                   "E-4291": "the endpoint returned too many consecutive failures"},
    },
    {
        "slug": "boreal_queue", "name": "Boreal Queue", "version": "5.0.4", "release": "2024-11-05",
        "owner": "Messaging Infrastructure Team", "purpose": "durable ordered message queueing for internal services",
        "rate_limit": 3000, "max_payload_mb": 2, "retention_days": 14,
        "auth": "mutual TLS", "token_ttl_min": 60, "sla": "99.99",
        "primary_region": "ap-southeast-1", "dr_region": "ap-northeast-1",
        "errors": {"E-4023": "the client certificate was rejected", "E-5109": "the partition leader is unavailable",
                   "E-4292": "the producer exceeded its quota"},
    },
    {
        "slug": "cinder_cache", "name": "Cinder Cache", "version": "1.7.3", "release": "2025-02-14",
        "owner": "Performance Engineering Team", "purpose": "low-latency key-value caching in front of databases",
        "rate_limit": 9000, "max_payload_mb": 1, "retention_days": 7,
        "auth": "static API keys", "token_ttl_min": 240, "sla": "99.50",
        "primary_region": "eu-north-1", "dr_region": "eu-west-1",
        "errors": {"E-4024": "the API key is not recognised", "E-5110": "the cache node is being rebalanced",
                   "E-4293": "the key lookup burst limit was exceeded"},
    },
    {
        "slug": "drift_gateway", "name": "Drift Gateway", "version": "4.4.2", "release": "2025-04-02",
        "owner": "API Platform Team", "purpose": "routing and throttling public API traffic",
        "rate_limit": 450, "max_payload_mb": 10, "retention_days": 60,
        "auth": "JWT bearer tokens", "token_ttl_min": 30, "sla": "99.95",
        "primary_region": "us-east-2", "dr_region": "us-west-1",
        "errors": {"E-4025": "the JWT audience claim is invalid", "E-5111": "no healthy upstream was available",
                   "E-4294": "the tenant throttle limit was exceeded"},
    },
    {
        "slug": "ember_stream", "name": "Ember Stream", "version": "0.9.8", "release": "2024-12-09",
        "owner": "Analytics Pipeline Team", "purpose": "streaming event ingestion for analytics workloads",
        "rate_limit": 15000, "max_payload_mb": 8, "retention_days": 21,
        "auth": "OAuth 2.0 device flow", "token_ttl_min": 20, "sla": "99.70",
        "primary_region": "sa-east-1", "dr_region": "us-east-1",
        "errors": {"E-4026": "the device code has expired", "E-5112": "the ingestion shard is backpressured",
                   "E-4295": "the stream write budget was exceeded"},
    },
]

_FILLER = [
    "{name} is deployed as a set of stateless services behind a load balancer.",
    "Configuration changes to {name} are rolled out gradually and can be reverted within minutes.",
    "Operational metrics for {name} are published to the shared dashboard every minute.",
    "Customer support can escalate {name} incidents to the on-call engineer at any time.",
]


def render_product_spec(p: dict) -> str:
    errors = "\n".join(f"- {code}: {meaning}." for code, meaning in p["errors"].items())
    filler = [f.format(name=p["name"]) for f in _FILLER]
    return f"""# {p['name']} Product Specification

## Overview

{p['name']} version {p['version']} was released on {p['release']} and is owned by the {p['owner']}. Its purpose is {p['purpose']}. {filler[0]}

## Limits

The default rate limit for {p['name']} is {p['rate_limit']} requests per minute per API key. The maximum request payload is {p['max_payload_mb']} MB. Data is retained for {p['retention_days']} days before it is deleted. {filler[1]}

## Authentication

{p['name']} authenticates clients using {p['auth']}. Access tokens are valid for {p['token_ttl_min']} minutes. {filler[2]}

## Availability

The primary region for {p['name']} is {p['primary_region']} and the disaster recovery region is {p['dr_region']}. The contractual SLA is {p['sla']}% monthly uptime. {filler[3]}

## Error codes

The following error codes are returned by {p['name']}:

{errors}
"""


RESUMES: list[dict] = [
    {
        "slug": "resume_marcus_bell", "name": "Marcus Bell", "title": "Senior Backend Engineer",
        "city": "Austin, TX", "years": 9,
        "skills": ["Python", "Go", "PostgreSQL", "Apache Kafka", "Kubernetes", "Terraform"],
        "jobs": [
            ("Northwind Logistics", "Senior Backend Engineer", "2021", "present",
             "Reduced p99 latency of the ledger service from 480 ms to 190 ms."),
            ("Helix Payments", "Backend Engineer", "2017", "2021",
             "Led the migration of 14 services to Kubernetes."),
        ],
        "education": "B.S. Computer Science, University of Texas at Austin, 2015",
        "cert": "AWS Certified Solutions Architect - Professional (2022)",
    },
    {
        "slug": "resume_priya_raman", "name": "Priya Raman", "title": "Data Engineer",
        "city": "Toronto, ON", "years": 7,
        "skills": ["Python", "Spark", "Airflow", "PostgreSQL", "dbt", "Snowflake"],
        "jobs": [
            ("Lakeview Analytics", "Senior Data Engineer", "2020", "present",
             "Cut nightly pipeline runtime from 6 hours to 95 minutes."),
            ("Maple Retail", "Data Engineer", "2018", "2020",
             "Built the customer segmentation warehouse used by 40 analysts."),
        ],
        "education": "M.Sc. Data Science, University of Waterloo, 2018",
        "cert": "Google Professional Data Engineer (2021)",
    },
    {
        "slug": "resume_tomas_weber", "name": "Tomas Weber", "title": "Site Reliability Engineer",
        "city": "Berlin, Germany", "years": 11,
        "skills": ["Go", "Kubernetes", "Prometheus", "Terraform", "Linux", "Python"],
        "jobs": [
            ("Nordlicht Cloud", "Staff SRE", "2019", "present",
             "Improved service availability from 99.5% to 99.95%."),
            ("Rheinbank IT", "Systems Engineer", "2013", "2019",
             "Automated 80% of manual deployment steps."),
        ],
        "education": "Dipl.-Ing. Informatik, TU Berlin, 2012",
        "cert": "Certified Kubernetes Administrator (2020)",
    },
    {
        "slug": "resume_aiko_tanaka", "name": "Aiko Tanaka", "title": "Machine Learning Engineer",
        "city": "Tokyo, Japan", "years": 6,
        "skills": ["Python", "PyTorch", "MLflow", "Kubernetes", "SQL", "Docker"],
        "jobs": [
            ("Sakura Robotics", "ML Engineer", "2021", "present",
             "Shipped a vision model that raised pick accuracy from 91% to 97%."),
            ("Kaze Mobility", "Junior ML Engineer", "2019", "2021",
             "Built the feature store serving 12 models."),
        ],
        "education": "M.Eng. Information Science, University of Tokyo, 2019",
        "cert": "TensorFlow Developer Certificate (2020)",
    },
    {
        "slug": "resume_diego_alvarez", "name": "Diego Alvarez", "title": "Frontend Engineer",
        "city": "Madrid, Spain", "years": 8,
        "skills": ["TypeScript", "React", "Next.js", "GraphQL", "Playwright", "CSS"],
        "jobs": [
            ("Solana Commerce", "Senior Frontend Engineer", "2020", "present",
             "Raised Lighthouse performance from 62 to 94 on the storefront."),
            ("Plaza Media", "Frontend Developer", "2016", "2020",
             "Introduced the component library adopted by 9 teams."),
        ],
        "education": "B.S. Software Engineering, Universidad Politecnica de Madrid, 2016",
        "cert": "Meta Front-End Developer Certificate (2019)",
    },
]


def render_resume(r: dict) -> str:
    jobs = "\n".join(
        f"{company} - {role} ({start} - {end}). {achievement}"
        for company, role, start, end, achievement in r["jobs"]
    )
    return f"""{r['name']}
{r['title']} | {r['city']} | {r['years']} years of experience

TECHNICAL SKILLS
{', '.join(r['skills'])}

EXPERIENCE
{jobs}

EDUCATION
{r['education']}

CERTIFICATIONS
{r['cert']}
"""


# SKU code, product, category, Q3 unit cost, Q2 unit cost, minimum order quantity
SKUS: list[tuple] = [
    ("HW-ND-2201", "Edge Node Mini", "Compute", "184.50", "176.25", 10),
    ("HW-ND-2210", "Edge Node Pro", "Compute", "412.75", "398.10", 5),
    ("HW-ND-2215", "Edge Node Max", "Compute", "899.90", "871.40", 2),
    ("HW-SW-3301", "Rack Switch 24P", "Networking", "265.30", "259.80", 4),
    ("HW-SW-3310", "Rack Switch 48P", "Networking", "498.65", "487.20", 3),
    ("HW-PW-4401", "Power Unit 1U", "Power", "72.15", "69.95", 20),
    ("HW-PW-4410", "Power Unit 2U", "Power", "131.45", "127.30", 10),
    ("HW-ST-5501", "Storage Tray 8TB", "Storage", "342.80", "355.60", 6),
    ("HW-ST-5510", "Storage Tray 16TB", "Storage", "611.25", "630.75", 4),
    ("HW-CB-6601", "Fiber Cable 10m", "Cabling", "9.85", "9.40", 100),
    ("HW-CB-6610", "Fiber Cable 30m", "Cabling", "18.20", "17.55", 50),
    ("HW-FN-7701", "Cooling Fan Kit", "Cooling", "27.90", "26.35", 25),
]

# Region, Q1, Q2, Q3 revenue in thousands of USD
REVENUE: list[tuple] = [
    ("North America", 4820, 5135, 5590),
    ("Europe", 3110, 3345, 3620),
    ("Asia Pacific", 2275, 2490, 2985),
    ("Latin America", 1040, 1130, 1245),
]

# Department, headcount at end of Q3
HEADCOUNT: list[tuple] = [
    ("Engineering", 184), ("Sales", 76), ("Customer Support", 63), ("Finance", 21), ("People Operations", 17),
]
