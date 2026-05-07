---
sidebar_position: 1
title: Overview
---

## What are Evals?

Evals are the process of measuring the abilities of an AI system to understand how well it performs and to improve it.

## Why do Evals?

In AI applications, outputs are not deterministic, and success/failure is subjective and context-dependent.

If you want to understand how your app actually works, where it's performing and where it's failing, you need to run evals. They give you concrete, measurable signals to guide improvements.

## How to do Evals systematically

1. **Define your evaluation criteria clearly.** What do you want to test? Write this in natural language.
2. **Get a test set.** A diverse collection of inputs that represent how real users interact with your application.
3. **Score the test set.** Either manually label outcomes yourself, or use a calibrated LLM as a judge.
4. **Iterate.** Make changes to your application and re-run evaluations to see if results improve.

## How can Kaleidoscope help?

Most evaluation tools today have gaps that make systematic evaluation harder than it needs to be.

### Most tools focus on safety evals

Kaleidoscope goes one step further to support general functional and utility evals, measuring whether your application actually does what your users need it to do.

### Static evaluations only

A lot of tools help you with static evaluations. You bring your test set and they will run an LLM judge for you. Kaleidoscope helps you generate realistic evaluation inputs tailored to your application, so you don't need to start with a pre-built dataset.

### Scores are hard to understand

LLM-as-a-Judge scoring is common in tools today, but its behaviour is abstracted from the user. As a result, users don't know whether the judge is truly trustworthy.

Kaleidoscope automatically creates an LLM-as-a-Judge based on your specific evaluation rubrics. It also provides a user-friendly annotation UI to enhance the human-in-the-loop experience. These annotations are then used to calculate judge reliability for transparency.

### Keeping the human in the loop

Most tools today accept the risks of fully automated evaluation. In certain domains though, you still want human oversight over automated evaluation, but most tools make annotation painful by requiring people to read through long AI outputs. 

Kaleidoscope focuses on making human review a good experience. The annotation UI breaks down AI responses into easy-to-review chunks, with judge reasoning highlighted for individual claims aimed at reducing friction and fatigue.

---

Ready to get started? [Install Kaleidoscope](./installation.md), then head to the [Quickstart](./quickstart.md).
