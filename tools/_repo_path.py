#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Make repo-local imports work when tools are executed as scripts."""

import os
import sys


def add_repo_root():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return repo_root
