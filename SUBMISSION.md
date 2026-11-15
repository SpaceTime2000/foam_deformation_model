# Publish the reviewed submission

The repository is not uploaded just because these files exist. Follow this checklist and check the resulting links before replying to the assignment email.

## 1. Create an empty public repository

On GitHub, create a public repository, for example `foam-deformation-from-video`. Leave GitHub's README, license and .gitignore initialization options unchecked: this project supplies its own README and ignore rules. Do not upload the whole folder using the browser; the included test video exceeds the browser's upload limit.

From the project root (one level above `scripts`):

```powershell
git init -b main
git add .
git status --short
```

Review the staged files. They should include the final five Python files, requirements and documentation; the two marked-video annotation sets and processed displacement observations/model; and the exported viewer, including its `video.mp4`. They should not include the assignment/paper PDFs, old `run.py` pipeline, original `data/train` videos, caches or generated visualization videos. Ignore rules do not delete or move those local files.

The viewer includes one approximately 93 MB test video, below GitHub's 100 MiB per-file limit. A warning about the file exceeding 50 MiB is expected. The approximately 128 MB training video must not be committed; original recordings are distributed through the Drive folder in step 3.

If the staged list is correct:

```powershell
git commit -m "Add video-fitted foam model and interactive test comparison"
$repoUrl = Read-Host "Paste the HTTPS URL of your empty GitHub repository"
git remote add origin $repoUrl
git push -u origin main
```

Git may prompt you to sign in through the browser. If the remote or repository already exists, inspect it before rerunning initialization or adding another remote.

## 2. Enable the viewer

In the repository, open **Settings → Pages**. Under **Build and deployment**, choose **Deploy from a branch**, select **main** and **/(root)**, then Save. Wait for GitHub's Pages deployment to finish and use the URL it displays.

The root page redirects to `viewer/dist/`. The `.nojekyll` file keeps this a plain static site. The hosted page shows the frozen export; it does not need Python, raw training footage or a backend.

Test the actual hosted URL in a signed-out/private browser window: switch presses, play the footage, scrub, rotate the proxy, select dots for the exploratory mean, and download parameters/metrics. Check that video seeking and the marker overlays work on the hosted copy. A successful local preview alone does not verify deployment.

## 3. Verify the footage download link

The README links to the [Google Drive input-footage folder](https://drive.google.com/drive/folders/1eDp1PoQyIxnEdt35SP5SI9YXnNkyjfJ6?usp=sharing). It should contain the original `marked_foam_train.mp4` and `marked_foam_test.mp4`. For rerunning processing, download them into `data/train/` and `data/test/`, respectively. The viewer retains its own test-video playback copy. A GitHub Release is not required for the footage.

Set folder access to **Anyone with the link → Viewer**, then use a signed-out/private browser window to verify that both videos are present and downloadable. The folder's existence alone does not establish access. Do not include the assignment PDF or supplied papers as project data. Before submitting, put the actual hosted viewer URL near the top of README.md, then commit and push that documentation update. The Drive link is already included.

The current annotation/cache path portability limitation is documented in the main README. The portable exported page reproduces the reported predictions; rerunning the original image processing on another machine currently needs setup review and regeneration. Do not claim a fully automatic raw-video reproduction until that is tested.

## 4. Final review and email

Confirm that the repository's main README is the current displacement-model explanation and that the final model is `data/processed/displacement/marked_foam_train/parameters.json`. The viewer's metrics include the instantaneous-recovery baseline. Keep limitations, missing observations and input reconstruction disclosures visible.

The reply needs the repository link and working result link. A concise draft is:

> Hi,
>
> Thank you for the extension. Here is my take-home submission:
>
> Repository: [insert verified repository URL]
>
> Interactive result: [insert verified viewer URL]
>
> The README explains the approach, how to run it, and the results and limitations. It also links to the input footage. The model uses measured book displacement as its boundary input and fits an effective recovery time from foam-marker motion, with evaluation on a separate recording. It does not identify stiffness and damping separately.
>
> Best,
> Tanish

Replace the bracketed fields with the verified links. Sending the email remains a separate user action.
