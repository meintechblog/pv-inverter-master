# Research Summary: v2.1 Dashboard Redesign & Polish

**Domain:** Embedded IoT dashboard, CSS animations, Venus OS Modbus integration
**Researched:** 2026-03-18
**Overall confidence:** MEDIUM-HIGH

## Executive Summary

The v2.1 milestone requires zero new dependencies. All five feature areas (CSS animations, toast notifications, Venus OS info, Apple-style toggles, peak statistics) are implementable with the existing stack of vanilla JS, CSS3, and Python/pymodbus.

CSS animations should use exclusively GPU-accelerated properties (`transform` and `opacity`) to maintain smooth 60fps rendering even on low-power devices like the Raspberry Pi that runs the Venus OS GUI. The existing codebase already has partial animation support (gauge arc transitions, value flash effects) which provides a solid foundation.

The toast notification system already exists in basic form (single toast, no stacking, no exit animation). Enhancement to support stacking, click-to-dismiss, and exit animations is straightforward vanilla JS work. The Venus OS info widget is the most complex addition because it requires a new Modbus TCP client connection to Venus OS at 192.168.3.146:502, reading system registers on Unit ID 100. However, much of the "Venus OS info" (override status, last contact, control state) is already tracked internally.

Peak statistics is the simplest feature -- a Python dataclass tracking daily peaks in-memory, integrated into the existing DashboardCollector snapshot pipeline.

## Key Findings

**Stack:** Zero new dependencies. CSS3 animations + vanilla JS patterns + pymodbus client for Venus OS reads.
**Architecture:** Venus OS client is the only new backend component. Frontend changes are CSS + JS enhancements to existing files.
**Critical pitfall:** Venus OS Modbus TCP must be enabled manually in Venus OS settings, and should be polled at max 5-10s intervals (not 1s like the SE30K).

## Implications for Roadmap

Based on research, suggested phase structure:

1. **CSS Foundation & Toggle** - Add animation variables, Apple-style toggle CSS, `prefers-reduced-motion` support
   - Addresses: Animation timing variables, toggle switch component
   - Avoids: Premature animation of elements not yet refactored

2. **Toast System Enhancement** - Upgrade existing toast to stacking, exit animation, warning variant
   - Addresses: Smart notifications infrastructure
   - Avoids: Building notification triggers before the notification system is solid

3. **Peak Statistics** - Add PeakStats dataclass, integrate into DashboardCollector
   - Addresses: Peak kW, operating hours, efficiency tracking
   - Avoids: Frontend display before backend data is available

4. **Venus OS Info Widget** - Optional Venus OS Modbus client, display in dashboard
   - Addresses: Battery SOC, grid power, system state from Venus OS
   - Avoids: Coupling to Venus OS before core dashboard is polished

5. **Unified Dashboard Layout** - Merge power control inline, add animations to all widgets
   - Addresses: Single-page dashboard, page transition animations, staggered widget entrance
   - Avoids: Layout refactor before all components exist

**Phase ordering rationale:**
- CSS foundation first because other features depend on animation variables
- Toast before other features because override/fault events need notifications
- Peak stats before Venus OS client because it is simpler and exercises the snapshot pipeline
- Venus OS client last because it is optional and the most complex new backend addition

**Research flags for phases:**
- Phase 4 (Venus OS Client): Needs validation that Modbus TCP is enabled on the Venus OS instance and that register addresses match the v3.71 firmware
- Phase 5 (Unified Layout): Standard CSS grid refactoring, unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| CSS Animations | HIGH | Well-documented browser standards, multiple 2025/2026 guides verified |
| Toast System | HIGH | Existing implementation to enhance, standard vanilla JS pattern |
| Apple Toggle | HIGH | Pure CSS technique, widely documented |
| Venus OS Registers | MEDIUM | Register addresses verified via community sources, not from official Excel sheet directly |
| Peak Statistics | HIGH | Simple in-memory pattern, no external dependencies |
| DVCC Status | LOW | Could not verify specific register address; recommend using existing override detection instead |

## Gaps to Address

- Venus OS register addresses need validation against the actual running Venus OS v3.71 instance (read a few registers and compare to expected values)
- DVCC status register address unknown -- recommend inferring DVCC from existing Venus OS write detection rather than reading a DVCC register
- The official CCGX-Modbus-TCP-register-list-3.70.xlsx should be downloaded and checked for accuracy of the register addresses listed in STACK.md
