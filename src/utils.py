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
