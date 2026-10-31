#!/usr/bin/env bash
# Creates this project's issue labels in siraj-samsudeen/feather-connect, or updates them if they exist.
# Rendered by Copier from .copier-answers.yml (repo, extra_labels): to change the labels, change
# the answers (copier update --trust --defaults --data ...) and run this again.
# Meanings: the issue-workflow skill, § Ratings.
set -euo pipefail

repo='siraj-samsudeen/feather-connect'

label() { gh label create "$1" --repo "$repo" --color "$2" --description "$3" --force; }

label red    d73a4a 'Blocker: has to be fixed'
label yellow fbca04 'Workable, but easy to get wrong'
label green  0e8a16 'Nice to have: blocks nothing major'
label chore  c5def5 'Maintenance with no behaviour change: dependencies, tooling, housekeeping'
