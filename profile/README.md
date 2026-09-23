<div align="center">

<!-- Wave without embedded title — text was clipping on capsule-render -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:0d2137,50:0a3d62,100:1a6591&height=140&section=header" />
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:d6eaf8,50:7eb8d9,100:0a3d62&height=140&section=header" />
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d2137,50:0a3d62,100:1a6591&height=140&section=header" alt="Kadeep Technologies banner" width="100%" />
</picture>

# Kadeep Technologies

**AI-native QA infrastructure** — led by **[Test Studios](https://teststudios.ai)**

<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=18&duration=3000&pause=1000&color=4FC3F7&center=true&vCenter=true&width=720&height=40&lines=Chat-first+QA+agent+for+web+%26+mobile;Explore+%C2%B7+flow+%C2%B7+run+%C2%B7+file+issues;Specialist+lanes+for+l10n+%26+accessibility" />
  <source media="(prefers-color-scheme: light)" srcset="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=18&duration=3000&pause=1000&color=0A3D62&center=true&vCenter=true&width=720&height=40&lines=Chat-first+QA+agent+for+web+%26+mobile;Explore+%C2%B7+flow+%C2%B7+run+%C2%B7+file+issues;Specialist+lanes+for+l10n+%26+accessibility" />
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=18&duration=3000&pause=1000&color=4FC3F7&center=true&vCenter=true&width=720&height=40&lines=Chat-first+QA+agent+for+web+%26+mobile;Explore+%C2%B7+flow+%C2%B7+run+%C2%B7+file+issues;Specialist+lanes+for+l10n+%26+accessibility" alt="Kadeep product tagline" />
</picture>

<br/>

[![Website](https://img.shields.io/badge/Website-kadeep.ai-0a3d62?style=for-the-badge)](https://kadeep.ai)
[![Test Studios](https://img.shields.io/badge/Flagship-Test_Studios-1a6591?style=for-the-badge)](https://teststudios.ai)
[![Demo](https://img.shields.io/badge/Book_Demo-Get_access-e74c3c?style=for-the-badge)](https://kadeep.ai/demo)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-KaDeep_AI-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/kadeep-ai)

<br/>

![Founded](https://img.shields.io/badge/Founded-2025-0a3d62?style=flat-square)
![HQ](https://img.shields.io/badge/HQ-Mumbai-0a3d62?style=flat-square)
![Focus](https://img.shields.io/badge/Focus-QA_Infrastructure-1a6591?style=flat-square)

</div>

---

## What we build

Kadeep builds AI-native QA products for teams that ship continuously.

**[Test Studios](https://teststudios.ai)** is the flagship — a chat-first QA agent with a real browser runtime and virtual mobile devices. Around it: test management, localization QA, and accessibility as specialist products.

> *“KaDeep helped us move from brittle automations to reliable agents. We finally have confidence in execution quality.”*
> — **Summit**, Product Manager, Setu

---

## Flagship — Test Studios

<div align="center">

### Chat-first QA agent for web & mobile

Talk to a senior QA engineer. It explores your app, writes natural-language flows, runs them in a browser or on a virtual device, files issues, and remembers what it learned.

<br/>

[![Open Test Studios](https://img.shields.io/badge/Open-teststudios.ai-0a3d62?style=for-the-badge)](https://teststudios.ai)
[![Book a Demo](https://img.shields.io/badge/Book_a_Demo-Talk_to_us-e74c3c?style=for-the-badge)](https://kadeep.ai/demo)

<br/>

![Category](https://img.shields.io/badge/Category-Chat--First_QA_Agent-0a3d62?style=flat-square)
![Surfaces](https://img.shields.io/badge/Surfaces-Web_%7C_Desktop_%7C_Mobile-1a6591?style=flat-square)
![Browser](https://img.shields.io/badge/Browser-Playwright-2ea44f?style=flat-square)
![Mobile](https://img.shields.io/badge/Mobile-Appetize-4FC3F7?style=flat-square&labelColor=0d2137)
![MCP](https://img.shields.io/badge/MCP-Supported-success?style=flat-square)

</div>

### Product model

```mermaid
flowchart LR
    subgraph Client["Clients"]
        W[Web]
        D[Desktop]
        M[Mobile]
    end

    subgraph TS["Test Studios"]
        Chat[Chat agent]
        Flows[Flows · suites · runs]
        Mem[Memory · issues · evidence]
    end

    subgraph Runtime["Execution"]
        PW[Playwright browser]
        AP[Appetize iOS / Android]
    end

    W --> Chat
    D --> Chat
    M --> Chat
    Chat --> Flows
    Chat --> Mem
    Flows --> PW
    Flows --> AP
```

### Capabilities

| Layer | What you get |
|:---|:---|
| **Agent** | Chat-first QA loop, skill-based specialization, natural-language flows |
| **Execution** | Playwright sessions, Appetize virtual devices, live view + artifacts |
| **Memory** | Governed layers (app / you / team), credentials in a separate vault |
| **Ops** | Suites, runs, issues from the conversation, MCP for Cursor / Claude |

---

## Platform map

```mermaid
flowchart TB
    K[Kadeep Technologies]

    K --> TS[Test Studios — flagship]
    K --> TM[app.kadeep.ai — test management]
    K --> LQ[GTW2 — localization QA]
    K --> AX[Axco — accessibility]

    TS --> Cap1[Explore web & mobile]
    TS --> Cap2[Flows · suites · runs]
    TS --> Cap3[Issues · evidence · memory]
```

---

## Which product should I use?

| Need | Product | Role |
|:---|:---|:---|
| Chat-driven exploratory + automated QA (web / mobile) | **[Test Studios](https://teststudios.ai)** | Flagship agent |
| Central cases, runs, coverage, go / no-go | **[app.kadeep.ai](https://app.kadeep.ai)** | Test management |
| Visual / localization QA across locales | **[GTW2](https://gtw2.ai)** | Localization specialist |
| Continuous WCAG monitoring | **[Axco](https://accessibility.kadeep.ai)** | Accessibility specialist |

---

## Specialist products

<table>
<tr>
<td width="33%" valign="top">

### [app.kadeep.ai](https://app.kadeep.ai)

![Type](https://img.shields.io/badge/Test_Management-0a3d62?style=flat-square)

AI-assisted cases, runs, defect sync, release go / no-go.

</td>
<td width="33%" valign="top">

### [GTW2](https://gtw2.ai)

![Type](https://img.shields.io/badge/Localization_QA-0a3d62?style=flat-square)

Agentic crawl across 50+ locales with visual QA reports.

</td>
<td width="33%" valign="top">

### [Axco](https://accessibility.kadeep.ai)

![Type](https://img.shields.io/badge/Accessibility-0a3d62?style=flat-square)

WCAG 2.1 / 2.2 checks, health scores, sprint fix plans.

</td>
</tr>
</table>

---

## How a release run works

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Team
    participant TS as Test Studios
    participant Spec as GTW2 / Axco
    participant Out as Issues / signals

    Dev->>TS: State a release goal in chat
    TS->>TS: Explore · run flows · collect evidence
    TS->>Spec: Call specialist lane when needed
    Spec-->>TS: Locale / a11y report
    TS->>Out: File issues · surface go / no-go
    TS-->>Dev: Evidence-backed result
```

---

## Why teams use Kadeep

| Pain | With Kadeep |
|:---|:---|
| Manual regression eats sprints | Test Studios explores and runs flows from chat |
| Only engineers can maintain brittle scripts | Natural-language flows + agent execution |
| L10n / a11y checked late or never | GTW2 and Axco as continuous specialist lanes |
| Siloed QA tools | One stack — flagship agent + specialists |

---

## Contact

<div align="center">

| | |
|:---|:---|
| **Test Studios** | [teststudios.ai](https://teststudios.ai) |
| **Company** | [kadeep.ai](https://kadeep.ai) |
| **Test management** | [app.kadeep.ai](https://app.kadeep.ai) |
| **Localization** | [gtw2.ai](https://gtw2.ai) |
| **Accessibility** | [accessibility.kadeep.ai](https://accessibility.kadeep.ai) |
| **LinkedIn** | [KaDeep AI](https://www.linkedin.com/company/kadeep-ai) |
| **Blog** | [kadeep.ai/blog](https://kadeep.ai/blog) |
| **Demo** | [kadeep.ai/demo](https://kadeep.ai/demo) |

<br/>

[![Book a Demo](https://img.shields.io/badge/Book_a_Demo-Get_access-e74c3c?style=for-the-badge)](https://kadeep.ai/demo)
[![Open Test Studios](https://img.shields.io/badge/Open-Test_Studios-0a3d62?style=for-the-badge)](https://teststudios.ai)

</div>

---

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:1a6591,50:0a3d62,100:0d2137&height=100&section=footer" />
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:0a3d62,50:7eb8d9,100:d6eaf8&height=100&section=footer" />
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:1a6591,50:0a3d62,100:0d2137&height=100&section=footer" alt="Kadeep Technologies footer" width="100%" />
</picture>

<sub>Kadeep Technologies · © 2025–2026</sub>

</div>
