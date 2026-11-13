"""
Sim Overhaul Studio - generated script mod.

Applies a studio project to sims by first/last name when a zone loads.
Also exposes console commands:

    simoverhaul.apply    - apply the overhaul now
    simoverhaul.report   - list sims that were matched / skipped

The script is defensive: every action is wrapped so that a missing pack,
outdated API or renamed tuning can never break the save.
"""
import base64
import json
import os
import traceback

import services
import sims4.log
from sims4.commands import Command, CommandType
from sims4.resources import Types

try:
    from sims4.tuning.instances import get_instance
except Exception:  # pragma: no cover
    get_instance = None

try:
    LOGGER = sims4.log.Logger('SimOverhaul', default_owner='SimOverhaulStudio')
except Exception:
    try:
        LOGGER = sims4.log.Logger('SimOverhaul')
    except Exception:
        LOGGER = None

CONFIG = json.loads(base64.b64decode('__CONFIG_B64__').decode('utf-8'))

_APPLIED = False
_REPORT = []


def _log(message):
    try:
        LOGGER.info(message)
    except Exception:
        pass


def _sim_key(sim_info):
    try:
        return (sim_info.first_name or '', sim_info.last_name or '')
    except Exception:
        return ('', '')


def _all_sim_infos():
    try:
        return list(services.sim_info_manager().values())
    except Exception:
        return []


def _find(by_name, first, last, household=''):
    candidates = by_name.get((first.lower(), last.lower()), [])
    if household:
        for info in candidates:
            try:
                hh = info.household.name or ''
            except Exception:
                hh = ''
            if hh.lower() == household.lower():
                return info
    return candidates[0] if candidates else None


def _get_instance(manager_type, instance_id):
    if not instance_id:
        return None
    try:
        manager = services.get_instance_manager(manager_type)
        return manager.get(int(instance_id))
    except Exception:
        return None


def _apply_traits(sim_info, trait_ids):
    for trait_id in trait_ids:
        try:
            trait = _get_instance(Types.TRAIT, trait_id)
            if trait is None:
                continue
            try:
                sim_info.add_trait(trait)
            except Exception:
                sim_info.trait_tracker.add_trait(trait)
        except Exception:
            _log('trait failed %s' % trait_id)


def _remove_traits(sim_info, trait_ids):
    for trait_id in trait_ids:
        try:
            trait = _get_instance(Types.TRAIT, trait_id)
            if trait is None:
                continue
            try:
                sim_info.remove_trait(trait)
            except Exception:
                sim_info.trait_tracker.remove_trait(trait)
        except Exception:
            _log('trait removal failed %s' % trait_id)


def _apply_milestones(sim_info, milestone_ids):
    for milestone_id in milestone_ids:
        try:
            milestone_type = getattr(Types, 'MILESTONE', None)
            if milestone_type is None:
                return
            milestone = _get_instance(milestone_type, milestone_id)
            if milestone is None:
                continue
            tracker = getattr(sim_info, 'milestone_tracker', None)
            if tracker is not None:
                tracker.add_milestone(milestone)
            else:
                sim_info.add_milestone(milestone)
        except Exception:
            _log('milestone failed %s' % milestone_id)


def _apply_skills(sim_info, skills):
    for skill in skills:
        try:
            statistic = _get_instance(Types.STATISTIC, skill.get('id'))
            if statistic is None:
                continue
            level = max(0, min(20, int(skill.get('level', 1))))
            tracker = sim_info.skill_tracker
            try:
                tracker.set_skill_level(statistic, level)
            except Exception:
                try:
                    tracker.set_skill_level(statistic, level, False)
                except Exception:
                    value = tracker.get_statistic(statistic)
                    if value is not None:
                        value.set_value(level)
        except Exception:
            _log('skill failed %s' % skill)


def _apply_career(sim_info, career_data):
    try:
        career = _get_instance(Types.CAREER, career_data.get('id'))
        if career is None:
            return
        tracker = sim_info.career_tracker
        tracker.add_career(career)
        level = int(career_data.get('level') or 1)
        try:
            career.career_level = max(1, min(10, level))
        except Exception:
            try:
                career.set_level(level)
            except Exception:
                pass
    except Exception:
        _log('career failed %s' % career_data)


def _apply_aspiration(sim_info, aspiration_data):
    try:
        aspiration = _get_instance(Types.ASPIRATION, aspiration_data.get('id'))
        if aspiration is None:
            return
        sim_info.aspiration_tracker.set_aspiration(aspiration)
    except Exception:
        _log('aspiration failed %s' % aspiration_data)


def _apply_funds(sim_info, funds):
    try:
        if funds is None:
            return
        sim_info.household.funds.money = max(0, int(funds))
    except Exception:
        _log('funds failed')


def _apply_relationship(sim_info, other_info, rel):
    try:
        friendship = float(rel.get('friendship', 0))
        romance = float(rel.get('romance', 0))
        tracker = sim_info.relationship_tracker
        other_id = other_info.sim_id
        try:
            tracker.add_relationship_score(other_id, friendship, romance)
        except Exception:
            try:
                tracker.set_relationship_score(other_id, friendship, romance)
            except Exception:
                tracker.add_relationship_score(other_id, friendship)
    except Exception:
        _log('relationship failed')


def _apply_relationship_bits(sim_info, other_info, bits):
    if not bits:
        return
    bit_type = getattr(Types, 'RELATIONSHIP_BIT', None)
    if bit_type is None:
        return
    for bit_data in bits:
        try:
            bit = _get_instance(bit_type, bit_data.get('id'))
            if bit is None:
                continue
            try:
                sim_info.relationship_tracker.add_relationship_bit(other_info.sim_id, bit)
            except Exception:
                sim_info.relationship_tracker.add_relationship_bit(bit, other_info.sim_id)
        except Exception:
            _log('relationship bit failed %s' % bit_data)


def _apply_family(sim_info, other_info, relation):
    try:
        genealogy = sim_info.genealogy
        relation = (relation or '').lower()
        if relation in ('parent', 'mother', 'father'):
            genealogy.add_parent(other_info)
        elif relation in ('child', 'son', 'daughter'):
            genealogy.add_child(other_info)
        elif relation in ('sibling', 'brother', 'sister'):
            genealogy.add_sibling(other_info)
    except Exception:
        _log('family failed')


def _occult_type(name):
    try:
        from sims.occult.occult_enums import OccultType
        mapping = {
            'vampire': OccultType.VAMPIRE,
            'spellcaster': OccultType.SPELLCASTER,
            'werewolf': OccultType.WEREWOLF,
            'mermaid': OccultType.MERMAID,
            'alien': OccultType.ALIEN,
            'ghost': OccultType.GHOST,
            'fairy': OccultType.FAIRY,
        }
        return mapping.get((name or '').lower())
    except Exception:
        return None


def _apply_occult(sim_info, name):
    if not name or name.lower() in ('human', 'none'):
        return
    occult = _occult_type(name)
    if occult is None:
        return
    try:
        sim_info.occult_tracker.add_occult(occult)
    except Exception:
        _log('occult failed %s' % name)


def apply_overhaul(force=False):
    global _APPLIED, _REPORT
    if _APPLIED and not force:
        return
    infos = _all_sim_infos()
    by_name = {}
    for info in infos:
        first, last = _sim_key(info)
        if first and last:
            by_name.setdefault((first.lower(), last.lower()), []).append(info)

    _REPORT = []
    for sim in CONFIG.get('sims', []):
        first = sim.get('first', '')
        last = sim.get('last', '')
        info = _find(by_name, first, last, sim.get('household', ''))
        if info is None:
            _REPORT.append('SKIP %s %s (not in save)' % (first, last))
            continue
        _apply_traits(info, [t.get('id') for t in sim.get('traits', [])])
        _remove_traits(info, [t.get('id') for t in sim.get('remove_traits', [])])
        _apply_milestones(info, [m.get('id') for m in sim.get('milestones', [])])
        _apply_traits(
            info,
            [p.get('id') for p in sim.get('likes', [])] + [p.get('id') for p in sim.get('dislikes', [])],
        )
        _apply_traits(info, [d.get('id') for d in sim.get('degrees', [])])
        _apply_skills(info, sim.get('skills', []))
        if sim.get('career'):
            _apply_career(info, sim['career'])
        if sim.get('aspiration'):
            _apply_aspiration(info, sim['aspiration'])
        if sim.get('funds') is not None:
            _apply_funds(info, sim['funds'])
        _apply_occult(info, sim.get('occult'))
        for rel in sim.get('relationships', []):
            target = None
            if '|' in rel.get('target', ''):
                a, b = rel.get('target', '').split('|', 1)
                target = _find(by_name, a, b, rel.get('target_household', ''))
            if target is not None:
                _apply_relationship(info, target, rel)
                _apply_relationship_bits(info, target, rel.get('bits', []))
        for fam in sim.get('family', []):
            target_key = fam.get('target', '')
            if '|' in target_key:
                a, b = target_key.split('|', 1)
                target = _find(by_name, a, b, fam.get('target_household', ''))
                if target is not None:
                    _apply_family(info, target, fam.get('relation'))
        _REPORT.append('OK   %s %s' % (first, last))

    _APPLIED = True
    _write_report()


def _write_report():
    try:
        folder = os.path.expanduser('~\\Documents\\Electronic Arts\\The Sims 4')
        path = os.path.join(folder, 'SimOverhaul_report.txt')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('Sim Overhaul Studio report\n')
            handle.write('==========================\n')
            handle.write('\n'.join(_REPORT))
        _log('report written to %s' % path)
    except Exception:
        _log(traceback.format_exc())


@Command('simoverhaul.apply', command_type=CommandType.Live)
def _cmd_apply(_connection=None):
    apply_overhaul(force=True)


@Command('simoverhaul.report', command_type=CommandType.Live)
def _cmd_report(_connection=None):
    _write_report()


try:
    from sims.zone import Zone
    from sims4.tuning.tunable import inject_to

    @inject_to(Zone, 'on_loading_screen_animation_finished')
    def _on_zone_loaded(original, self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            apply_overhaul()
        except Exception:
            _log(traceback.format_exc())
        return result
except Exception:
    _log('Zone hook unavailable; use the simoverhaul.apply command')
