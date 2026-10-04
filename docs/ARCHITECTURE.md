# Architecture

> Headings only for now — content is filled in during Phase 0 step 0.7.

## Overview

## Layer diagram

## Folder responsibilities

## Data flow

## Decision log

- **SerpApi empty results:** SerpApi returns an `error` field with the message "Google hasn't returned any results for this query." for valid queries that yield no results. Rather than raising `SerpApiError`, `SerpApiClient` treats this as a valid empty response and logs status `empty`. Phase 1 parsers must treat a missing `jobs_results` or `organic_results` array as zero items.

## Known limits

- SerpApi queries yielding zero results return `{"error": "Google hasn't returned any results for this query."}` without `jobs_results` or `organic_results` arrays. Phase 1 parsers must treat a missing `jobs_results` or `organic_results` array as zero items.

