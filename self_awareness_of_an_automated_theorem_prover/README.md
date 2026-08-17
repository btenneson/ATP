# Formalized Self-Awareness in Automated Theorem Provers

This directory is the canonical home in this repository for the **Depths of Induction and Formalized Self-Awareness** material and its lecture companions.

## Terminology and scope

Here, **self-awareness** is a technical term for formal self-reference, representation of proof activity, and provability/reflection structure. It does **not** mean consciousness, subjective experience, sentience, or phenomenal awareness.

The purpose of the formalism is narrower: to ask what a sufficiently specified automated theorem prover can express and prove about its own proof relation, its own proof claims, and iterated layers of such claims.

## Current corrected edition

The current corrected edition designated for this directory is:

- [`Depths_of_Induction_and_Formalized_Self_Awareness_v46.1.pdf`](Depths_of_Induction_and_Formalized_Self_Awareness_v46.1.pdf)

This file is copied byte-for-byte from the repository-root file `Depths_of_Induction_and_Formalized_Self_Awareness_V46_1_Corrected_Edition.pdf`; the root copy is retained so existing links are not broken.

**Source status:** no matching LaTeX source for this corrected v46.1 document was located in this repository during the 2026-08-17 cleanup. No source file has been reconstructed or invented here.

## Formalization status

The existing exposition introduces an internal provability notation with an intended meaning, but that notation should not by itself be read as already supplying a full arithmetized Gödel proof predicate with all standard derivability conditions.

For the rigorous bridge from the abstract hierarchy to conventional proof theory, see:

- [`FORMALIZATION_REPAIR.md`](FORMALIZATION_REPAIR.md)

That companion note specifies the recommended `Prf_M` / `Prov_M` construction, distinguishes metatheoretic soundness from same-theory reflection, and replaces unrestricted self-reflection with a stratified reflection architecture when appropriate.

The companion note is a clarification and forward formalization plan. It does not silently alter the claims in the preserved PDF.

## Lecture material

The `lecture/` directory contains:

- `Lecture_15_3_to_15_6_Natural_Delivery_Transcript.txt`
- `Lecture_Sections_15_3_to_15_6.mp3`

The lecture is useful as an informal guide to the internal provability predicate, the reflection sequence, levels, gaps in the level set, and the role of additional reliability assumptions.

## Archive

The `archive/` directory preserves earlier material:

- `Depths_and_Self_Awareness_Merged_v2.pdf`
- `Depths_and_Self_Awareness_labeled_pages_58-59.pdf`

These are retained for provenance and comparison, not presented as the current corrected edition.

## Repository hygiene

The former directory named `self awareness of an automated theorem prover` is retained only as a compatibility pointer to this directory. Its old binary contents were relocated here, and the accidental Windows `desktop.ini` file was removed from that publication path.
