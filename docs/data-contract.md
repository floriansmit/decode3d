# DECODE first-pass data contract

The regional calculation unit is one projected XY cell and one named reservoir. Geological properties and calculation results are stored separately.

## Coordinates

- Horizontal CRS: ED50 / UTM zone 32N (`EPSG:23032`)
- Source vertical reference: elevation relative to mean sea level
- `top_depth` and `base_depth`: positive metres below MSL
- Web display coordinates: WGS84 derived from the source CRS

## Geological and reservoir variables

| Variable | Unit | Meaning |
|---|---:|---|
| `top_depth` | m bMSL | Positive depth to reservoir top |
| `base_depth` | m bMSL | Positive depth to reservoir base |
| `thickness_mean` | m | Gross interval thickness |
| `thickness_sd` | m | Uncertainty in cell-scale gross thickness |
| `net_thickness` | m | Gross thickness multiplied by NTG |
| `ntg` | 1 | Net-to-gross fraction |
| `porosity` | 1 | Effective net-reservoir porosity |
| `permeability` | mD | Effective horizontal permeability |
| `ln_permeability_mean` | ln(mD) | Natural logarithm of permeability |
| `ln_permeability_sd` | 1 | Standard deviation in natural-log space |
| `transmissivity` | Dm | Permeability multiplied by net thickness |
| `temperature` | °C | First-pass midpoint temperature |
| `confidence` | 1 | Provisional confidence score |
| `valid_mask` | 1 | Whether first-pass screening criteria pass |

## Provenance

Every dataset states geometry, property, and temperature sources independently. The current geometry comes from the delivered EarthVision horizons. Property values and uncertainties are provisional priors and must be replaced by the well and GO-Forward workflows before scientific publication.

