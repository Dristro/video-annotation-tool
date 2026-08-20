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
