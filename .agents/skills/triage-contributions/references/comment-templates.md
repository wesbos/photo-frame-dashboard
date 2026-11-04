# Comment templates

Comments go out under the owner's GitHub account. Keep them short, specific and kind. Say what
happened, why, and what would be welcome next. Never quote private data back.

Append the required bot-comment footer from [the skill](../SKILL.md#6-comment-and-close) to
every template below, including short replies and closure comments.

## Merged with changes

> Merged, thanks! One change after merging: [what changed], because [why, in one sentence].
> [Optional: what was not tested on hardware.]

## Merged, the code came from another PR

> Merged, thanks: [what was taken] is in. The [feature] came from #[N] instead, because [one-sentence
> reason]. I updated your [doc] to match.

## Harvested and closed

> Thanks! [The facts] are now in [link to the doc/row]. We're not merging [the scripts/tree] as they
> are, because [specific reasons, as a short list]. [A focused follow-up] would be very welcome.

## Changes requested (left open)

Use only after trying to fix the problem yourself. Do not request revisions for cleanup the
triage agent can do.

> Thanks! I [what was investigated or fixed]. The remaining blocker is [specific missing evidence,
> hardware result, asset or decision]. Could you [smallest action needed to unblock it]?

## Out of scope (closed)

> Thanks for writing this up. It's out of scope for this repo, which is about unlocking frames plus
> a demo dashboard. It would fit well as a link from
> [Community Builds](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/community-builds.md).

## Superseded (closed)

> Thanks! #[N] landed with the same [feature], and it also [extra fix]. Closing this one as covered
> by #[N].

## Issue answered by the docs (closed)

> Thanks for the report! It's now in [the firmware table / device index / U-Boot table](<link>).
> Closing as documented. Please reopen if something there doesn't match what you saw.

## Issue still open

> This is still unsolved, so I'm leaving it open. [What has fixed similar problems for others, with
> a link.] If any of these change what you see, please post the result here.

## Direct question

Answer the question first, with the facts and links. Then the caveats as a short list. Then
whether the issue stays open.
