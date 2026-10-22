# CI image fixture

`paper.jpg` is the existing project paper sample, copied here solely for repeatable Docker inference tests. The expected detection class is `paper`. The Docker build context excludes this directory; CI uploads the image only after starting the container. Runtime uploads remain ignored by Git.
