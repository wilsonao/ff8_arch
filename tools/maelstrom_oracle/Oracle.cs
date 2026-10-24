using System;
class Oracle {
  static void Main() {
    int[] seeds = { 0, 1, 2, 3, 4, 5, 12345, -7, 2147483647, -2147483648, 161803398, 98400790 };
    foreach (var s in seeds) {
      var r = new Random(s);
      var sb = new System.Text.StringBuilder();
      sb.Append(s).Append(':');
      for (int i = 0; i < 12; i++) sb.Append(' ').Append(r.Next(245));
      for (int i = 0; i < 12; i++) sb.Append(' ').Append(r.Next(0, 61));
      for (int i = 0; i < 4; i++) sb.Append(' ').Append(r.Next());
      for (int i = 0; i < 4; i++) sb.Append(' ').Append(r.Next(-1, int.MaxValue));
      Console.WriteLine(sb.ToString());
    }
  }
}
