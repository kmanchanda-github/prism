---
title: Prism Incident Analysis
emoji: 🔍
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI-powered multi-agent incident analysis platform
---

# Prism — AI-Powered Incident Analysis

Prism runs a multi-agent LangGraph pipeline to analyse production incidents. Submit an incident, and three parallel agents (log analyst, code analyst, defect analyst) produce a synthesized root-cause report with recommended actions.

## Usage

1. Set `ANTHROPIC_API_KEY` in Space secrets (Settings → Repository secrets)
2. Open the Space URL — you'll see the Submit form
3. Paste in an incident title, description, and severity — or use the demo scenario below

## Demo Scenario

```
Title:    Checkout service timeout spike — payment failures
Severity: P1
Description: Starting ~14:32 UTC, checkout service returned 504s on ~40% of
             payment requests. Error rate went from 0.2% to 38%.
             Rolled back deploy d9f3a1c at 15:05, recovered by 15:12.
Metadata: {"service":"checkout-service","deploy_sha":"d9f3a1c"}
```

## Architecture

```
Incident → route_decision (LLM) → [parallel] log_agent · code_agent · defect_agent
         → synthesizer → quality_check (retry if confidence < 0.7)
         → React UI: report · chat · version history · export
```

## Source

[github.com/kmanchanda-github/prism](https://github.com/kmanchanda-github/prism)
