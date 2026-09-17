"""The achievement catalogue. Rules live in services; this is the seeded definition data.

Migrations 0002 and 0004 keep their own frozen copies, so editing this list later needs a new
migration (or an update in the admin).
"""

FIRST_STEP = "first-step"
INDEPENDENT_THINKER = "independent-thinker"
ON_A_ROLL = "on-a-roll"
CONSISTENT_LEARNER = "consistent-learner"
SKILL_MASTERED = "skill-mastered"
BOSS_CLEARED = "boss-cleared"
TEN_DOWN = "ten-down"
PROJECT_BUILDER = "project-builder"

ACHIEVEMENTS = (
    {
        "code": FIRST_STEP,
        "title": "First Step",
        "description": "Complete your first exercise correctly.",
        "icon_key": "footsteps",
        "rarity": "common",
        "order": 1,
    },
    {
        "code": INDEPENDENT_THINKER,
        "title": "Independent Thinker",
        "description": "Complete an exercise correctly without hints, explanations or solutions.",
        "icon_key": "lightbulb",
        "rarity": "uncommon",
        "order": 2,
    },
    {
        "code": ON_A_ROLL,
        "title": "On a Roll",
        "description": "Learn on 3 days in a row.",
        "icon_key": "flame",
        "rarity": "common",
        "order": 3,
    },
    {
        "code": CONSISTENT_LEARNER,
        "title": "Consistent Learner",
        "description": "Learn on 7 days in a row.",
        "icon_key": "calendar",
        "rarity": "rare",
        "order": 4,
    },
    {
        "code": SKILL_MASTERED,
        "title": "Skill Mastered",
        "description": "Master every concept in a skill.",
        "icon_key": "star",
        "rarity": "rare",
        "order": 5,
    },
    {
        "code": BOSS_CLEARED,
        "title": "Boss Cleared",
        "description": "Complete your first Boss Challenge.",
        "icon_key": "trophy",
        "rarity": "epic",
        "order": 6,
    },
    {
        "code": TEN_DOWN,
        "title": "Ten Down",
        "description": "Complete 10 different exercises correctly.",
        "icon_key": "target",
        "rarity": "uncommon",
        "order": 7,
    },
    {
        "code": PROJECT_BUILDER,
        "title": "Project Builder",
        "description": "Complete your first project.",
        "icon_key": "hammer",
        "rarity": "rare",
        "order": 8,
    },
)
