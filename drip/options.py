# -*- coding: utf-8 -*-
"""Options.

Created on Sat Mar  5 14:50:35 2022

@author: travis
"""
import dash_bootstrap_components as dbc

INDICES = [
    {"label": "CPC RI", "value": "ri"},
    {"label": "PDSI", "value": "pdsi"},
    {"label": "PDSI-Self Calibrated", "value": "scpdsi"},
    {"label": "Palmer Z Index", "value": "pzi"},
    {"label": "EDDI-1", "value": "eddi1"},
    {"label": "EDDI-2", "value": "eddi2"},
    {"label": "EDDI-3", "value": "eddi3"},
    {"label": "EDDI-6", "value": "eddi6"},
    {"label": "SPI-1", "value": "spi1"},
    {"label": "SPI-2", "value": "spi2"},
    {"label": "SPI-3", "value": "spi3"},
    {"label": "SPI-6", "value": "spi6"},
    {"label": "SPEI-1", "value": "spei1"},
    {"label": "SPEI-2", "value": "spei2"},
    {"label": "SPEI-3", "value": "spei3"},
    {"label": "SPEI-6", "value": "spei6"}
]

INDEX_NAMES = {
    "ri": "NOAA CPC-Derived Rainfall Index",
    "pdsi": "Palmer Drought Severity Index",
    "scpdsi": "Self-Calibrated Palmer Drought Severity Index",
    "pzi": "Palmer Z Index",
    "spi1": "Standardized Precipitation Index - 1 month",
    "spi2": "Standardized Precipitation Index - 2 month",
    "spi3": "Standardized Precipitation Index - 3 month",
    "spi4": "Standardized Precipitation Index - 4 month",
    "spi5": "Standardized Precipitation Index - 5 month",
    "spi6": "Standardized Precipitation Index - 6 month",
    "spi7": "Standardized Precipitation Index - 7 month",
    "spi8": "Standardized Precipitation Index - 8 month",
    "spi9": "Standardized Precipitation Index - 9 month",
    "spi10": "Standardized Precipitation Index - 10 month",
    "spi11": "Standardized Precipitation Index - 11 month",
    "spi12": "Standardized Precipitation Index - 12 month",
    "spei1": "Standardized Precipitation-Evaporation Index - 1 month",
    "spei2": "Standardized Precipitation-Evaporation Index - 2 month",
    "spei3": "Standardized Precipitation-Evaporation Index - 3 month",
    "spei4": "Standardized Precipitation-Evaporation Index - 4 month",
    "spei5": "Standardized Precipitation-Evaporation Index - 5 month",
    "spei6": "Standardized Precipitation-Evaporation Index - 6 month",
    "spei7": "Standardized Precipitation-Evaporation Index - 7 month",
    "spei8": "Standardized Precipitation-Evaporation Index - 8 month",
    "spei9": "Standardized Precipitation-Evaporation Index - 9 month",
    "spei10": "Standardized Precipitation-Evaporation Index - 10 month",
    "spei11": "Standardized Precipitation-Evaporation Index - 11 month",
    "spei12": "Standardized Precipitation-Evaporation Index - 12 month"
}

RETURNS = [
    {"label": "Indemnities", "value": "indemnity"},
    {"label": "Index", "value": "index_array"},
    {"label": "Loss Ratios", "value": "loss_ratio"},
    {"label": "Net Payouts", "value": "net_payout"},
    {"label": "Payment Calculation Factors", "value": "pcf"},
    {"label": "Payout Frequencies", "value": "frequency"},
    {"label": "Producer Premiums", "value": "premium_producer"},
    {"label": "Subsidies", "value": "subsidy"},
]
