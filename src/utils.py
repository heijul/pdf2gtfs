def __uid_generator():
    """ Infinite sequence of ids. """
    next_id = 0
    while True:
        yield next_id
        next_id += 1


# Override the __uid_generator, to ensure uniqueness.
__uid_generator = __uid_generator()


def next_uid():
    """ Returns the next unique id. IDs are shared by all objects. """
    return next(__uid_generator)


def contains_bbox(container_bbox, bbox):
    return (container_bbox[0] <= bbox[0] <= container_bbox[2] and
            container_bbox[1] <= bbox[1] <= container_bbox[3] and
            container_bbox[0] <= bbox[2] <= container_bbox[2] and
            container_bbox[1] <= bbox[3] <= container_bbox[3])


