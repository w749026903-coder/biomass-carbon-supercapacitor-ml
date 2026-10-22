"""Keep legitimate >100% retention; separate units, raw predictions and reliability."""
from collections import defaultdict
import math
import numpy as np
from models.v1_0.model import Encoder, CORE, MATERIAL, weights

SEMANTIC = ['activation_primary_chemistry', 'activation_stage_status', 'precursor_origin_class']


def derive_semantics(record):
    """Project taxonomy from already reviewed methods; never infer from a target or sample ID."""
    agent = record.get('activation_agent_v14')
    applicability = record.get('activation_applicability_v14') or ''
    precursor = (record.get('precursor_v14') or '').lower()
    if agent:
        upper = agent.upper()
        if 'KOH' in upper or 'NAOH' in upper:
            chemistry = 'hydroxide_containing'
        elif upper == 'H3PO4':
            chemistry = 'phosphoric_acid'
        elif upper == 'K2CO3':
            chemistry = 'carbonate'
        elif upper == 'KMNO4':
            chemistry = 'permanganate'
        elif upper == 'KNO3':
            chemistry = 'nitrate'
        elif upper == 'ZNCL2':
            chemistry = 'zinc_chloride'
        elif agent == 'potassium citrate/zinc acetate template-assisted pyrolysis':
            chemistry = 'template_salt_mixture'
        else:
            raise ValueError('Unreviewed activation chemistry: ' + agent)
        stage = 'chemical_or_template_stage_reported'
    elif 'nonactivated' in applicability:
        chemistry, stage = 'explicit_nonactivated_control', 'explicit_nonactivated_control'
    elif 'without chemicals or template' in applicability:
        chemistry, stage = 'explicit_no_chemical_or_template', 'direct_pyrolysis_without_chemical_template'
    else:
        # Absence of a described separate step does not prove absence of an agent.
        chemistry = None
        stage = 'no_separate_activation_reported' if 'no separate activation' in applicability else None
    if any(s in precursor for s in ['cellulose', 'cotton pulp', 'chitosan', 'alginate']):
        origin = 'processed_biopolymer'
    elif any(s in precursor for s in ['algae', 'spirulina']):
        origin = 'algal_biomass'
    elif any(s in precursor for s in ['apricot', 'reed', 'coconut', 'wood', 'straw', 'herbal',
                                      'kochia', 'walnut', 'rapeseed', 'chestnut', 'leaves', 'onion', 'nut skin',
                                      'sesame', 'sawdust']):
        origin = 'plant_residue'
    else:
        origin = None  # CCL/AMFS abbreviations are not expanded by guessing.
    return dict(zip(SEMANTIC, [chemistry, stage, origin]))


class PositiveRetentionModel:
    def __init__(self, specification):
        self.spec = dict(specification)

    def fit(self, records):
        from sklearn.linear_model import Ridge
        self.encoder = Encoder(self.spec).fit(records)
        self.semantic_schema = []
        if self.spec['block'] == 'material':
            for field in SEMANTIC:
                support = defaultdict(set)
                for record in records:
                    if record.get(field) is not None:
                        support[record[field]].add(record['source_group'])
                self.semantic_schema.append({'field': field, 'minimum_sources': 3,
                    'source_support': {k:len(v) for k,v in sorted(support.items())},
                    'vocabulary': sorted(k for k,v in support.items() if len(v) >= 3)})
        X = self.transform(records)
        y = np.asarray([r['retention_pct'] for r in records])
        if np.any(y <= 0):
            raise ValueError('This experimental log-target recipe requires positive observed targets.')
        z, w = np.log(y / 100.), weights(records)
        self.center = float(np.average(z, weights=w))
        self.scale = math.sqrt(float(np.average((z-self.center)**2, weights=w))) or 1.
        self.estimator = Ridge(alpha=self.spec['alpha'], solver='svd')
        self.estimator.fit(X, (z-self.center)/self.scale, sample_weight=w)
        self.training_sources = sorted({r['source_group'] for r in records})
        self.training_endpoint_ids = [r['endpoint_id'] for r in records]
        return self

    def transform(self, records):
        numeric = self.encoder.transform(records)
        categorical = []
        for record in records:
            row = []
            for item in self.semantic_schema:
                value = record.get(item['field'])
                row += [float(value == v) for v in item['vocabulary']]
                row += [float(value is not None and value not in item['vocabulary']), float(value is None)]
            categorical.append(row)
        return np.concatenate([numeric, np.asarray(categorical).reshape(len(records), -1)], axis=1)

    def predict(self, records):
        z = self.estimator.predict(self.transform(records))*self.scale+self.center
        with np.errstate(over='raise', invalid='raise'):
            values = 100.*np.exp(z)
        if not np.all(np.isfinite(values)) or np.any(values <= 0):
            raise ValueError('Finite positive model output required; no silent clipping.')
        return values

    def predict_with_context(self, records):
        for record in records:
            if record.get('system') != '3E' or record.get('method') != 'GCD':
                raise ValueError('Explicit3E/GCD purpose required.')
            for field in CORE:
                if record.get(field) is None:
                    raise ValueError('Required protocol field missing: ' + field)
            if record['cycle_count'] < 1000 or record['reported_current_A_g'] <= 0 or record['concentration_mol_L'] <= 0:
                raise ValueError('Outside positive protocol inputs and >=1000-cycle purpose.')
            if record['cycle_voltage_lower_V'] >= record['cycle_voltage_upper_V']:
                raise ValueError('Lower voltage must be below upper voltage.')
        predictions = self.predict(records)
        outputs = []
        for record, value in zip(records, predictions):
            flags = self.encoder.warnings(record)
            for item in self.semantic_schema:
                v = record.get(item['field'])
                if v is None:
                    flags.append('semantic_missing:'+item['field'])
                elif v not in item['vocabulary']:
                    flags.append('semantic_rare_or_unseen:'+item['field'])
            outputs.append(assess_prediction(float(value), flags))
        return outputs


def assess_prediction(predicted_pct, input_warnings=None):
    if isinstance(predicted_pct, bool) or not isinstance(predicted_pct, (float,int)) or not math.isfinite(predicted_pct):
        raise ValueError('Explicit finite percentage value required.')
    if predicted_pct < 0:
        raise ValueError('Negative capacitance retention is invalid; do not silently set it to zero.')
    return {'predicted_retention_pct': predicted_pct, 'predicted_retention_ratio': predicted_pct/100.,
        'display': f'{predicted_pct:.2f}%', 'above_initial_reference': predicted_pct > 100,
        'interpretation': 'prediction_above_reference_not_experimental_activation_evidence' if predicted_pct > 100 else 'prediction_relative_to_initial_reference',
        'reliability_status': 'exploratory_not_independently_validated', 'reliable_for_design': False,
        'input_warnings': list(input_warnings or []), 'calibrated_prediction_interval': None,
        'notice': 'In-range inputs and absence of warnings do not establish prediction accuracy.'}
