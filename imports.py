# Common imports used across the project
# Organized by category for better maintainability

# Standard Library
import asyncio
import atexit
import json
import logging
import math
import os
import random
import signal
import statistics
import sys
import time
import traceback
from datetime import datetime
from os import system
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# Third Party Libraries
import aiohttp
import nextcord
import requests
from nextcord.ext import commands, tasks

# Project Utilities
from utils.command_tracker import usage_tracker
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from utils.scalability import initialize_scalability