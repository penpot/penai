import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def plot_image_grid(
    images: list[Image.Image | np.ndarray],
    n_cols: int | None = None,
    figsize_per_image: float = 4,
    show_axis: bool = False,
) -> plt.Figure:
    """Plot a grid of images."""
    if n_cols is None:
        n_cols = int(np.ceil(np.sqrt(len(images))))

    n_rows = int(np.ceil(len(images) / n_cols))

    fig, axs = plt.subplots(
        n_rows,
        n_cols,
        figsize=(n_cols * figsize_per_image, n_rows * figsize_per_image),
    )

    for ax, image in zip(axs.flat[: len(images)], images, strict=True):
        ax.imshow(image)

        if not show_axis:
            ax.axis("off")

    for ax in axs.flat[len(images) :]:
        ax.axis("off")

    plt.tight_layout()

    return fig
