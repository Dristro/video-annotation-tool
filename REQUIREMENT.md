# Requirements

This file describes what the tool must be able to do once development is complete.

Tool overview:
--------------
This is a video annotation tool, it will allow the user to crop videos to length
without changing any raw video files. The tool must only generate annotation files
mapping a certain video clip to the annotations applied. For instance, if the user
chooses to cut a certain video from `start_time` to `end_time`, the raw clip must
stay untouched, the annotation file must map that video to a certain start and end
time.

## Functional requirements

1. Open video
2. Have video editing space
3. Opened videos must render in real-time in the editing space
4. Select videos directory and move through all videos in dir like a playlist
5. Mark video as annotated once annotation is complete. Reflect annotated video on preview
6. Annotations include: cut and label. A video can have multiple cuts, each cut has a
   start and end time along with a label. Labels is a set that is pre-defined during
   project initialization (the set must be editable after project is created).
7. Project must only create some project files and an annotation file that is public.
8. Project files must be saved to a specified directory that is decided in project
   initialization. Again, this dir must be editable, if changed after project initialized,
   then move all project files to new project-dir.
9. Scores (optional, per-project): alongside the label for a cut, the user may also record
   one or more named numeric scores. Scoring is off by default and toggled on/off per
   project in project settings. When enabled, the project defines a set of named scores
   (any name the user wants, any number of them), each with its own numeric range and its
   own dtype (float or int). Range defaults to 0-100, dtype defaults to float, when a new
   score is defined; both are editable per score, and the score set itself is editable after
   project creation (add/remove/rename score, same as labels). When scoring is enabled, every
   defined score is a required field when adding a cut: the input starts empty (no pre-filled
   value) and a cut cannot be added until every score has a valid, in-range value of the
   correct dtype. Values outside the defined range must be rejected, not accepted/clamped.
   Renaming a score updates it across all cuts already recorded with it, same as renaming a
   label. If a score is added to project settings after cuts already exist, those existing
   cuts are not retroactively required to have it -- they are simply flagged as incomplete
   (missing that score) rather than blocked or auto-filled. Each score may also have a
   description, shown in the score editor, describing what it means.
10. Editing an existing annotation: an annotation (cut) that already exists -- including one
    flagged incomplete because it predates a score, or a video's worth of cuts added before
    scoring was turned on at all -- must be editable, not just delete-and-recreate-able.
    Selecting an annotation (e.g. by clicking it on the video progress bar/timeline) loads its
    current label and scores into the same input area used to add a new one, so the user can
    fill in what's missing or correct what's there, then save the change back onto that same
    annotation.


## Non-functional requirements

1. Video playback must be fast for videos smaller than 5mins each.
2. Pre-load a certain chunk of a video thats next in playlist-queue for faster loading.
3. The UI must look and feel good, similar placement of objects to davinci-resolve.
4. The software is expected to run on macOS Tahoe on a MacBook-Pro M3-Pro. Ignore other devices for now.
5. Use pre-existing tools where applicable, do not write everything from scatrch.
6. Keep the software light-weight, low RAM and system usage (CPU + GPU).
7. Maintain under 4GB RAM usage at all times. If pre-loading a video doesn't fit in RAM, try
   fetching a starting chunk and load remaining after video is loaded into rendering region.
8. Fast, snappy clip generation.
9. Easy to distinguish annotated and non-annotated videos

## Definitions

### Anootated video:
* A video for which there exists an entry in the annotations mapping file.
* The entry may be empty, but that is only allowed if the user presses an annotated button to
  confirm empty video mapping as annotated.
* If the video doesn't have any entries in the mapping table, then its marked as not-annotated.
* A video loaded into the SW, but no annotations are created or annotated button is not clicked is
  marked as not annotated.

### Cutting a clip:
* Unlike traditional video editing, the videos here only mark a start and end time of a cut
  and store that information to the annotations.
* Each video can have multiple cuts.
* A cut can be given a label from a set of labels.

### Labels:
* A string associated with a cut.
* Only valid from a set of labels, initialized in the start of project and edited later (if required).
* Custom shortcuts must be allowed, the label editor will allow editing labels by allowing: add label,
  remove selected label(s), edit label. Edit label allows changing the label name and shortcut.
  If label name changes, then annotation file must also reflect the updated label name for all annotated
  videos so far.

### Scores:
* An optional, per-project feature: enabled/disabled as a whole via a project setting.
* A named numeric field that can be recorded on a cut, alongside its label. A project can define
  any number of scores, each with its own name, numeric range (min/max), and dtype (float or int).
* Default range is 0-100 and default dtype is float when a score is first defined; both are then
  editable per score, same as a label's shortcut is editable.
* When scoring is enabled, every currently-defined score is a required field on the "add cut" form:
  it starts with no pre-filled value, and the cut cannot be added until a valid, in-range value of
  the correct dtype has been entered for every score. Out-of-range or wrong-dtype values must be
  rejected outright, not silently clamped into range.
* Editing a score's name updates that key across every cut that already recorded a value under the
  old name, same as renaming a label updates the label text across existing cuts.
* Adding a new score after cuts already exist does not retroactively require or block those existing
  cuts -- they are simply flagged as incomplete (missing that score) so the user can go back and fill
  it in if they choose to, without anything being enforced.
* A score may have a description (free text) explaining what it means, editable alongside its name/
  range/dtype in the score editor.
