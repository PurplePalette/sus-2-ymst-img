from dataclasses import dataclass


class TapType:
    Normal = 1
    Critical = 2


# タップノーツ
@dataclass
class TapNote:
    tick: int
    lane: int
    width: int
    type: int  # 1: 通常ノーツ, 2: クリティカルノーツ


class FlickDirection:
    Up = 1
    Left = 3
    Right = 4


# フリックノーツ
@dataclass
class FlickNote:
    tick: int
    lane: int
    width: int
    direction: int  # 1: 上, 3: 左, 4: 右


# スクラッチノーツ
@dataclass
class Scratch:
    tick: int
    lane: int
    width: int


class HoldType:
    Normal = 0
    Critical = 1
    Scratch = 2
    ScratchCritical = 3
    Start = 4


# ホールドノーツ
@dataclass
class Hold:
    tick: int
    end_tick: int
    lane: int
    width: int
    type: int  # HoldType
    gimmick_type: int
    movement: int
    scratch_start: bool


@dataclass
class HoldScratch:
    tick: int
    lane: int
    width: int
    movement: int


@dataclass
class Sound:
    tick: int
    lane: int
    width: int
    type: int


@dataclass
class HoldEighth:
    tick: int
    lane: int
    width: int


class NoteType:
    None_ = 0
    Normal = 10
    Critical = 20
    Sound = 30
    SoundPurple = 31
    Scratch = 40
    Flick = 50
    HoldStart = 80
    CriticalHoldStart = 81
    ScratchHoldStart = 82
    ScratchCriticalHoldStart = 83
    Hold = 100
    CriticalHold = 101
    ScratchHold = 110
    ScratchCriticalHold = 111
    HoldEighth = 900


class GimmickType:
    None_ = 0
    JumpScratch = 1
    OneDirection = 2
    Split1 = 11
    Split2 = 12
    Split3 = 13
    Split4 = 14
    Split5 = 15
    Split6 = 16
