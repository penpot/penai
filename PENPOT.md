# Penpot

This is a brief description of page and shape attributes. It is based on the type definitions found in `common/src/app/common/types` folder.

## Pages

Everything in Penpot is contained into a Page, a page has the following attributes:

- `:id`: a UUID that identifies the page uniquely.
- `:name`: the name of the page.
- `:objects`: a vector of maps with every shape (object) contained in that page.
- `:options`: extra information about the page.
  - `:background`: rgb color for the background of the page.
  - `:saved-grids`: grids (not related to grid layouts) show on the page.
  - `:flows`: flows defined in the interactions tab.
  - `:guides`: guides shown on the page.

## Shape base attributes

A shape has a variable amount of attributes depending on its `:type`. But here are the attributes that are shared by all types of shapes, these are considered _base attributes_.

- `:id`: It's an UUID that identifies a shape uniquely. Every page has a root shape with `:type` `:frame` and `:id` `00000000-0000-0000-0000-000000000000`.
- `:type`: Specifies the type of the shape. These are the allowed values for this property: `:frame`,`:rect`,`:circle`,`:bool`,`:group`,`:image`,`:svg-raw`,`:path` and `:text`.
- `:name`: The name of the shape.
- `:selrect`: It's a rect with the selection rectangle of the shape.
- `:points`: A list of points for the top left, top right, bottom left and bottom right points of the `:selrect`.
- `:transform`: A matrix for the shape transformation.
- `:transform-inverse`: The inverse matrix of the shape transformation.
- `:parent-id`: The UUID of the parent shape or `00000000-0000-0000-0000-000000000000` for the root frame.
- `:frame-id`: The frame UUID where this shape is contained. `00000000-0000-0000-0000-000000000000` for the root frame

## Shape geometry attributes

There are a few other attributes that all shared by almost every type, with the exception of `:path`s and `:bool`s. These are called _geometry attributes_ and are:

- `:x`: The x coordinate of the shape.
- `:y`: The y coordinate of the shape.
- `:width`: The width of the shape.
- `:height`: The height of the shape.

## Shape attributes

These apply to every shape except `:frame`s.

- `:component-id`: UUID of the component.
- `:component-file`: UUID of the file that contains the component.
- `:component-root`: UUID of the root shape of the component.
- `:main-instance`: A boolean indicating that this is the main instance of the component.
- `:remote-synced`: A boolean indicating that the component is synced with it's remote origin.

- `:shape-ref`: TODO

- `:blocked`: A boolean indicating that this shape is blocked.
- `:collapsed`: A boolean indicating that this shape is collapsed in the tree view (left side bar).
- `:locked`: A boolean indicating that this shape is locked.
- `:hidden`: A boolean indicating that this shape is hidden.
- `:masked-group`: A boolean indicating that this shape is a masked group.
- `:fills`: A vector of fills.
- `:strokes`: A vector of strokes.
- `:proportion`: A number indicating the proportion (the relative scale of this shape).
- `:proportion-lock`: A boolean indicating that the proportion is locked.
- `:constraints-h`: A value indicating which constraints are applied to this shape horizontally.
- `:constraints-v`: A value indicating which constraints are applied to this shape vertically.
- `:fixed-scroll`: A boolean indicating that this element has a fixed scroll.
- `:blend-mode`: A value indicating which blend mode we're going to use when aplying blending to this shape.
- `:opacity`: A value between 0 and 1 indicating it's opacity.
- `:shadow`: A vector of shadows.
- `:blur`: A blur map.
- `:exports`: A vector of exports.
- `:interactions`: A vector of interactions.

## Frame attributes

- `:shapes`: This is a vector with all the UUIDs of the contained shapes.
- `:hide-fill-on-export`: This is a boolean specifying if we should hide the frame fill on export (to make it transparent).
- `:show-content`: This is a boolean
- `:hide-in-viewer`: This is a boolean specifying that this frame should not be visible on the viewer.

## Image attributes

- `:metadata`: This is a map with the following attributes:
  - `:width`: The original image width.
  - `:height`: The original image height.
  - `:mtype`: The image MIME type.
  - `:id`: An UUID identifying the image.

## Path attributes

- `:content`: This is a vector of path commands. Like the ones specified in [SVG Paths](https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths) but in our case we only have the following commands: `:line-to`, `:close-path`, `:move-to` and `:curve-to`.

A path command is a map that has a `:command` attribute and series of parameters:

```clojure
{
  :command :line-to
  :params {
    :x 24
    :y 42
  }
}
```

Commands `:move-to` and `:line-to` have two parameters `:x` and `:y`, while `:curve-to` has 6 parameters `:x`, `:y`, `:c1x`, `:c1y`, `:c2x` and `:c2y`. These values represent the parameters of the bezier-curve formed with the origin point (being the previous command coordinates) and the destination coordinates `:x` and `:y` and controls points `c1` and `c2`. `:close-path` doesn't have parameters.

## Text attributes

- `:grow-type`: Indicates how the shape grows `:auto-width`, `:auto-height` or `:fixed`.
- `:content`: This can be `nil` or a map that have two attributes `:type` set to `:root` and `:children` being a vector containing only one map, with the attributes `:type` set to `:paragraph-set` and `:children` being a vector of maps with the `:type` `:paragraph`. A paragraph can contain multiple maps without a `:type` attribute, these maps are considered leaf nodes of this tree and they always should have a attribute called `:text` containing the represented text in that part of the paragraph.

Example:

```clojure
:content {
  :type :root
  :children [
    { :type :paragraph-set
      :children [
        { :type :paragraph
          :children [
            {
              :text "Hello, World!"
            }
          ]
        }
      ]
    }
  ]
}
```

- `:position-data`:

### Text root attributes

- `:vertical-align`: This value is an enum of possible vertical alignments `:align-top`, `:align-center` and `:align-bottom`.

### Text paragraph-set attributes

This node doesn't have any extra attributes.

### Text paragraph attributes

- `:fills`: This is a vector of text fills applied to this paragraph.
- `:font-family`: Font family.
- `:font-size`: Font size in pixels.
- `:font-style`: Font style.
- `:font-weight`: Font weight.
- `:direction`: This can `:ltr` or `:rtl`. Left-to-right or Right-to-left text direction.
- `:text-decoration`: Text decoration.
- `:text-transform`: Text transform.
- `:typography-ref-id`: `nil` or an UUID to a typography defined in a file.
- `:typography-ref-file`: `nil` or an UUID to a the file that defines that typography.

### Text leaf node attributes

These attributes overrides the default values of the paragraph.

- `:fills`: This is a vector of text fills applied to this paragraph.
- `:font-family`: Font family.
- `:font-size`: Font size in pixels.
- `:font-style`: Font style.
- `:font-weight`: Font weight.
- `:direction`: This can `:ltr` or `:rtl`. Left-to-right or Right-to-left text direction.
- `:text-decoration`: Text decoration.
- `:text-transform`: Text transform.
- `:typography-ref-id`: `nil` or an UUID to a typography defined in a file.
- `:typography-ref-file`: `nil` or an UUID to a the file that defines that typography.

## Bool attributes

- `:shapes`: A vector with the shapes that are being used in the boolean operation.
- `:bool-type`: The boolean operation.
- `:bool-content`: A vector of maps with the commands generated by the boolean operation.

## Group attributes

- `:shapes`: The shapes contained in this group.

## Rect attributes

- `:rx`: Border radius applied in the x axis.
- `:ry`: Border radius applied in the y axis.
- `:r1`: Border radius of the top left side of the shape.
- `:r2`: Border radius of the top right side of the shape.
- `:r3`: Border radius of the bottom left side of the shape.
- `:r4`: Border radius of the bottom right side of the shape.

## Circle and SVG Raw attributes

These shape types doesn't have any extra attributes.

## Fills and strokes

Fills and strokes can be one of three types: `color`, `image` and `gradient`.

### Fill attributes

- `:fill-color`: Contains a hexadecimal representation of the color like `#000000`.
- `:fill-color-ref-file`: UUID identifying in which file the color reference is stored.
- `:fill-color-ref-id`: UUID identifying a color reference.
- `:fill-opacity`: A value between 0 and 1 specifying the amount of opacity.
- `:fill-image`: A map with an image that represents the image.
  - `:id`: UUID identifying the image.
  - `:name`: name.
  - `:width`: image width.
  - `:height`: image height.
  - `:mtype`: image MIME type.
  - `:keep-aspect-ratio`: A boolean indicating that we should keep the aspect ratio on rendering.
- `:fill-color-gradient`:
  - `:type`: Could be `:linear` or `:radial`.
  - `:start-x`: Initial x coordinate of the gradient.
  - `:start-y`: Initial y coordinate of the gradient.
  - `:end-x`: Final x coordinate of the gradient.
  - `:end-y`: Final y coordinate of the gradient.
  - `:width`: TODO
  - `:stops`: The amount of color stops we have in this gradient.

### Stroke attributes

- `:stroke-color`: Stroke color.
- `:stroke-color-ref-file`: UUID identifying in which file the color reference is stored.
- `:stroke-color-ref-id`: UUID identifying a color reference.
- `:stroke-opacity`: The stroke opacity.
- `:stroke-style`: The style of the stroke: `:dotted`, `:dashed`, `:mixed`, `:none` or `:svg`.
- `:stroke-width`: The width of the stroke.
- `:stroke-alignment`: Where the stroke is aligned:`:center`, `:inner` or `:outer`.
- `:stroke-cap-start`: The type of cap start.
- `:stroke-cap-end`: The typo of cap end.
- `:stroke-color-gradient`: Same structure as the `:fill-color-gradient`.
- `:stroke-image`: Same structure as the `:fill-image`
