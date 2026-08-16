-- Restores the original spelling of buyer/supplier names (as published by the
-- source), alongside the accent-stripped name_normalised used for matching.
-- See docs/entity_matching.md: name_normalised intentionally throws away
-- information (accents, casing, legal suffixes) that the product still needs
-- to show a citizen the exact name the government published.

alter table mart.suppliers
    add column if not exists display_name text;

alter table mart.buyers
    add column if not exists display_name text;
