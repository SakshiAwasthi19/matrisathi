// Categorical chart colours in fixed order (never cycled). Validated with the
// dataviz validator on the white card surface (light mode): all checks pass;
// slot 2 (marigold) is below 3:1 contrast, so every chart that uses it shows
// direct value labels and a screen-reader table.
export const SERIES = ["#008f86", "#e8952a", "#6a5acd"] as const;
