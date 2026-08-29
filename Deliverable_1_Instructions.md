# Deliverable 1
**Universidad de Concepción**
**Course:** Generative Artificial Intelligence (580694), Spring 2026
**Due:** August 31, 2026, 23:59
**Weight:** 10% of the semester project

## 1. Objective
The semester project asks your team to use a small open-weight language model with at most 8 billion parameters, which can carry out a complex real-world task that it fails at when prompted directly. Deliverable 1 builds the foundation for that work. Your team of up to four members defines the task, justifies its selection, and proposes three small open-weight language models that can solve it.

## 2. Requirements
* **Task selection:** Choose a specific, non-trivial task that a small model cannot solve reliably when asked directly. Then explain the failure. A vague diagnosis here weakens everything that follows, since the rest of the semester consists of attacking the specific failure you identify.
* **Model choice:** Select an open-weight model of at most 8 billion parameters. The model must run on your hardware or inside a free Google Colab GPU instance.

The task for the rest of the semester will be the same. If either is ambiguous or too easy, it will require iteration in the next deliverables.

## 3. Format and submission
* Submit a single-page PDF compiled from LaTeX, laid out as a poster or executive summary. Multi-page submissions and PDFs not produced in LaTeX will be rejected.
* Upload the PDF to Canvas before 23:59 on August 31.

## 4. Evaluation rubric
* **Task specification (10 points):** The task is defined clearly enough that a reader can tell what counts as a correct output.
* **Failure diagnosis (10 points):** The team identifies why direct prompting breaks down on this task and supports the claim with evidence.
* **Model candidates (10 points):** Three open-weight models under the parameter limit are proposed, with reasoning for why each suits the task and justification based on benchmarking.
* **Bonus (up to 3 points):** Awarded to teams whose candidate models are meaningfully smaller than the 8B ceiling, provided the choice is defended on task grounds and not on size alone.
* **Execution feasibility (10 points):** The team provides evidence that the proposed setup can actually run on the hardware available to them.
* **Repository (10 points):** The link works and the repository documents the task, the team, and the state of the work.
* **Format and writing (10 points):** One page, compiled from LaTeX, is well organized and clearly written.
