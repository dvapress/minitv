import 'package:flutter_test/flutter_test.dart';
import 'package:leapdrama/img.dart';

void main() {
  group('imgUrl', () {
    test('asks the pull zone for a width/quality variant', () {
      expect(
        imgUrl('https://cdn.leapdrama.local/covers/113/cover.jpg', 480),
        'https://cdn.leapdrama.local/covers/113/cover.jpg?width=480&quality=75',
      );
    });

    test('keeps the cache-busting version param', () {
      expect(
        imgUrl('https://cdn.leapdrama.local/covers/113/cover.jpg?v=17', 180),
        'https://cdn.leapdrama.local/covers/113/cover.jpg?v=17&width=180&quality=75',
      );
    });

    test('never double-sizes a url', () {
      const sized = 'https://cdn.leapdrama.local/covers/113/cover.jpg?width=960';
      expect(imgUrl(sized, 480), sized);
    });

    test('leaves other hosts untouched (google avatars, marketing site)', () {
      const avatar = 'https://lh3.googleusercontent.com/a/abc=s96-c';
      expect(imgUrl(avatar, 144), avatar);
    });

    test('returns empty for a missing cover', () {
      expect(imgUrl(null, 480), '');
      expect(imgUrl('', 480), '');
    });
  });
}
