import argparse
import sys

import sus

from .ytypes import (
    FlickDirection,
    FlickNote,
    GimmickType,
    Hold,
    HoldEighth,
    HoldType,
    NoteType,
    Scratch,
    Sound,
    TapNote,
    TapType,
)


class Sus2Ymst:
    def __init__(self, sus_filename: str):
        with open(sus_filename, "r") as file:
            self.score: sus.Score = sus.load(file)

    def on_hold_start(self, note: sus.Note):
        for hold in self.score.slides:
            hold_start = hold[0]
            if (
                note.tick == hold_start.tick
                and note.lane == hold_start.lane
                and note.width == hold_start.width
            ):
                return True
        return False

    def on_hold(self, flick_note: sus.Note):
        for hold in self.score.slides:
            hold_start = hold[0]
            hold_end = hold[-1]
            if (
                hold_start.tick < flick_note.tick < hold_end.tick
                and hold_start.lane == flick_note.lane
                and hold_start.width == flick_note.width
            ):
                return True
        return False

    def on_hold_end(self, flick_note: sus.Note):
        for hold in self.score.slides:
            hold_end = hold[-1]
            if (
                flick_note.tick == hold_end.tick
                and flick_note.lane <= hold_end.lane
                and flick_note.lane + flick_note.width >= hold_end.lane + hold_end.width
            ):
                return True
        return False

    def get_direction(self, flick_note: sus.Note):
        for directional in self.score.directionals:
            if (
                directional.tick == flick_note.tick
                and directional.lane == flick_note.lane
                and directional.width == flick_note.width
            ):
                return directional.type
        return None

    def tick_to_sec(self, tick: int) -> float:
        # BPM beats per minute 60秒間に何拍あるか[拍/分]
        # 60秒 / BPM = 1拍の秒数=4分音符の秒数[sec]
        # bar_length、拍数*bar_length=で1小節の長さになる
        # 480[tick]=4分音符の長さ
        # 1[sec/tick] = 4分音符の秒数 / 480

        # BPM変化なし
        if len(self.score.bpms) == 1:
            return (tick / 480) * (60 / self.score.bpms[0][1])
        # BPM変化あり
        bpm_index = 0
        for i, bpm in enumerate(self.score.bpms):
            if tick > bpm[0]:
                bpm_index = i
            else:
                break
        sec = 0
        for i, bpm in enumerate(self.score.bpms[:bpm_index]):
            sec += (
                ((self.score.bpms[i + 1][0] - self.score.bpms[i][0]) / 480)
                * 60
                / self.score.bpms[i][1]
            )
        sec += (
            ((tick - self.score.bpms[bpm_index][0]) / 480)
            * 60
            / self.score.bpms[bpm_index][1]
        )
        return sec

    def convert(self, lane_flag=False) -> str:
        ticks_per_beat_request = (
            [
                int(request.split()[1])
                for request in self.score.metadata.requests
                if request.startswith("ticks_per_beat")
            ]
            if self.score.metadata.requests
            else []
        )
        ticks_per_beat = ticks_per_beat_request[0]
        if ticks_per_beat != 480:
            print("tick_per_beat must be 480")
            sys.exit(1)
        tap_notes = []
        scratch_notes = []
        flick_notes = []
        for tap in self.score.taps:
            if tap.type == 1:
                # 通常ノーツ
                tap_notes.append(TapNote(tap.tick, tap.lane, tap.width, TapType.Normal))
            elif tap.type == 2:
                # クリティカルノーツ
                if not self.on_hold_start(tap):
                    # タップクリティカル
                    tap_notes.append(
                        TapNote(tap.tick, tap.lane, tap.width, TapType.Critical)
                    )
            elif tap.type == 3:
                # フリックノーツ
                if self.on_hold(tap):
                    # ホールド中
                    scratch_notes.append(Scratch(tap.tick, tap.lane, tap.width))
                elif not self.on_hold_end(tap):
                    # フリック
                    direction = self.get_direction(tap)
                    if direction is None:
                        direction = FlickDirection.Up
                    flick_notes.append(
                        FlickNote(tap.tick, tap.lane, tap.width, direction)
                    )

        hold_notes = []
        sound_notes = []
        hold_eighth_notes = []
        sus_flick_notes = list(filter(lambda note: note.type == 3, self.score.taps))
        slides = sorted(self.score.slides, key=lambda slide: slide[0].tick)
        for hold in slides:
            start_note = hold[0]
            end_note = hold[-1]
            conntection_note = hold[1:-1]
            hold_type = HoldType.Normal
            gimmick_type = GimmickType.None_
            movement = 0
            scratch_start = False
            # クリティカルかどうか
            for note in self.score.taps:
                if (
                    note.tick == start_note.tick
                    and note.lane == start_note.lane
                    and note.width == start_note.width
                    and note.type == TapType.Critical
                ):
                    hold_type |= HoldType.Critical
                    break
            # スクラッチで始まるかどうか
            for note in sus_flick_notes:
                if (
                    note.tick == start_note.tick
                    and note.lane <= start_note.lane
                    and note.lane + note.width >= start_note.lane + start_note.width
                ):
                    scratch_start = True
            # スクラッチで終わるかどうか
            for note in sus_flick_notes:
                if (
                    note.tick == end_note.tick
                    and note.lane == end_note.lane
                    and note.lane == end_note.lane
                    and note.width == end_note.width
                    and self.get_direction(note) == FlickDirection.Up
                ):  # 同じ大きさのスクラッチで終わる
                    hold_type |= HoldType.Scratch
                    gimmick_type = GimmickType.None_
                    movement = 0
                    break
                elif (
                    note.tick == end_note.tick
                    and note.lane == end_note.lane
                    and self.get_direction(note) == FlickDirection.Right
                ):
                    hold_type |= HoldType.Scratch
                    gimmick_type = GimmickType.JumpScratch
                    movement = note.width
                    break
                elif (
                    note.tick == end_note.tick
                    and note.lane + note.width == end_note.lane + end_note.width
                    and self.get_direction(note) == FlickDirection.Left
                ):
                    hold_type |= HoldType.Scratch
                    gimmick_type = GimmickType.JumpScratch
                    movement = -note.width
                    break

            # 中継点
            if len(conntection_note) > 0:
                if hold_type == HoldType.Normal or hold_type == HoldType.Critical:
                    sound_type = NoteType.Sound
                else:
                    sound_type = NoteType.SoundPurple
                for note in conntection_note:
                    sound_notes.append(
                        Sound(note.tick, note.lane, note.width, sound_type)
                    )

            # 8分判定
            for eighth_tick in range(start_note.tick, end_note.tick, 480 // 2):
                if eighth_tick == start_note.tick:
                    continue
                if eighth_tick >= end_note.tick:
                    break
                hold_eighth_notes.append(
                    HoldEighth(eighth_tick, start_note.lane, start_note.width)
                )

            hold_notes.append(
                Hold(
                    start_note.tick,
                    end_note.tick,
                    start_note.lane,
                    start_note.width,
                    hold_type,
                    gimmick_type,
                    movement,
                    scratch_start,
                )
            )

        all_notes = (
            tap_notes
            + scratch_notes
            + flick_notes
            + hold_notes
            + sound_notes
            + hold_eighth_notes
        )

        # ノーツのtick順にソート
        all_notes.sort(key=lambda note: note.tick)

        notation_txt = ""
        for note in all_notes:
            t = self.tick_to_sec(note.tick)
            if lane_flag:
                lane = note.lane + 1
            else:
                lane = note.lane - 2 + 1
            if isinstance(note, TapNote):
                if note.type == TapType.Normal:
                    notation_txt += f"{t:.4f},-1.0,{NoteType.Normal},{lane},{note.width},{GimmickType.None_},{0}\n"
                elif note.type == TapType.Critical:
                    notation_txt += f"{t:.4f},-1.0,{NoteType.Critical},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, Scratch):
                notation_txt += f"{t:.4f},-1.0,{NoteType.Scratch},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, FlickNote):
                notation_txt += f"{t:.4f},-1.0,{NoteType.Flick},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, Hold):
                end_t = self.tick_to_sec(note.end_tick)
                if note.gimmick_type == GimmickType.JumpScratch:
                    gimmick_type = "JumpScratch"
                else:
                    gimmick_type = note.gimmick_type
                if not note.scratch_start:
                    if note.type == HoldType.ScratchCritical:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.ScratchCriticalHoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchCriticalHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    elif note.type == HoldType.Scratch:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.ScratchHoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    elif note.type == HoldType.Critical:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.CriticalHoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.CriticalHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    else:
                        notation_txt += f"{t:.4f},-1.0,{NoteType.HoldStart},{lane},{note.width},{GimmickType.None_},0\n"
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.Hold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                else:
                    if note.type == HoldType.ScratchCritical:
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchCriticalHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
                    elif note.type == HoldType.Scratch:
                        notation_txt += f"{t:.4f},{end_t:.4f},{NoteType.ScratchHold},{lane},{note.width},{gimmick_type},{note.movement}\n"
            elif isinstance(note, Sound):
                notation_txt += f"{t:.4f},-1.0,{note.type},{lane},{note.width},{GimmickType.None_},{0}\n"
            elif isinstance(note, HoldEighth):
                notation_txt += f"{t:.4f},-1.0,{NoteType.HoldEighth},{lane},{note.width},{GimmickType.None_},{0}\n"
        return notation_txt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert sus to ymst")
    parser.add_argument("sus_file", help="sus file path")
    parser.add_argument(
        "-o",
        "--output_file",
        help="output file path",
        default="notation.txt",
        required=False,
    )
    args = parser.parse_args()

    sus2ymst = Sus2Ymst(args.sus_file)

    notation_txt = sus2ymst.convert()

    with open(args.output_file, "w") as f:
        f.write(notation_txt)
